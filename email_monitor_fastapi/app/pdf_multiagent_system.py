"""
PDF Processing Multi-Agent System using Google's Agent Development Kit
"""

from google.adk.agents import LlmAgent, Agent
from google.adk.tools import Tool
from typing import Dict, Any, List
import logging
from pathlib import Path
import json


class PDFPreProcessingAgent(LlmAgent):
    """Agent responsible for pre-processing PDF files"""
    
    def __init__(self):
        super().__init__(
            name="pdf_preprocessor",
            model="gemini-2.0-flash-thinking",
            instruction="""You are a PDF pre-processing specialist. Your tasks:
            1. Validate PDF file integrity
            2. Extract metadata from PDF files
            3. Determine optimal processing strategy
            4. Prepare files for main processing
            
            Always provide structured output with validation status and processing recommendations.""",
            description="Validates and prepares PDF files for processing"
        )
        self.logger = logging.getLogger(f"agent.{self.name}")


class PDFPostProcessingAgent(LlmAgent):
    """Agent responsible for post-processing PDF results"""
    
    def __init__(self):
        super().__init__(
            name="pdf_postprocessor", 
            model="gemini-2.0-flash-thinking",
            instruction="""You are a PDF post-processing specialist. Your tasks:
            1. Validate extracted content quality
            2. Format and structure the output
            3. Generate summaries and insights
            4. Create final reports
            
            Ensure all output is properly formatted and meets quality standards.""",
            description="Validates and formats PDF processing results"
        )
        self.logger = logging.getLogger(f"agent.{self.name}")


class PDFTools:
    """Collection of tools for PDF processing agents"""
    
    @staticmethod
    def validate_pdf_file(file_path: str) -> Dict[str, Any]:
        """Tool to validate PDF file integrity"""
        try:
            from pathlib import Path
            pdf_path = Path(file_path)
            
            if not pdf_path.exists():
                return {"valid": False, "error": "File does not exist"}
            
            if pdf_path.suffix.lower() != '.pdf':
                return {"valid": False, "error": "Not a PDF file"}
                
            file_size = pdf_path.stat().st_size
            
            return {
                "valid": True,
                "file_path": str(pdf_path),
                "file_size": file_size,
                "file_size_mb": round(file_size / (1024 * 1024), 2)
            }
            
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    @staticmethod
    def extract_pdf_metadata(file_path: str) -> Dict[str, Any]:
        """Tool to extract metadata from PDF"""
        try:
            # This is a placeholder - you would integrate with PyPDF2 or similar
            metadata = {
                "title": "Sample Title",
                "author": "Sample Author", 
                "subject": "Sample Subject",
                "creator": "Sample Creator",
                "pages": 10,
                "creation_date": "2025-01-01",
                "modification_date": "2025-01-01"
            }
            return {"success": True, "metadata": metadata}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def format_extraction_results(raw_content: Dict[str, Any]) -> Dict[str, Any]:
        """Tool to format PDF extraction results"""
        try:
            formatted = {
                "text_content": raw_content.get("text", ""),
                "tables": raw_content.get("tables", []),
                "images": raw_content.get("images", []),
                "structure": {
                    "paragraphs": len(raw_content.get("text", "").split("\n\n")),
                    "word_count": len(raw_content.get("text", "").split()),
                    "table_count": len(raw_content.get("tables", []))
                }
            }
            return {"success": True, "formatted_content": formatted}
            
        except Exception as e:
            return {"success": False, "error": str(e)}


class BeforeAgentCallback:
    """Callback executed before agent processing"""
    
    @staticmethod
    def log_start(agent_name: str, task_data: Dict[str, Any]) -> bool:
        """Log agent start with task details"""
        logger = logging.getLogger(f"callback.{agent_name}")
        logger.info(f"Starting {agent_name} with task: {task_data.get('task_type', 'unknown')}")
        
        # Validate required inputs
        if not task_data.get('file_path'):
            logger.error("Missing required file_path in task data")
            return False
            
        return True
    
    @staticmethod
    def validate_inputs(agent_name: str, task_data: Dict[str, Any]) -> bool:
        """Validate agent inputs before processing"""
        logger = logging.getLogger(f"callback.{agent_name}")
        
        required_fields = ['file_path', 'task_type']
        missing = [field for field in required_fields if not task_data.get(field)]
        
        if missing:
            logger.error(f"Missing required fields: {missing}")
            return False
            
        logger.info(f"Input validation passed for {agent_name}")
        return True


class AfterAgentCallback:
    """Callback executed after agent processing"""
    
    @staticmethod
    def log_completion(agent_name: str, task_data: Dict[str, Any], result: Dict[str, Any]):
        """Log agent completion with results"""
        logger = logging.getLogger(f"callback.{agent_name}")
        
        success = result.get('success', False)
        status = "SUCCESS" if success else "FAILED"
        
        logger.info(f"Completed {agent_name}: {status}")
        
        if not success and result.get('error'):
            logger.error(f"Error in {agent_name}: {result['error']}")
    
    @staticmethod
    def save_results(agent_name: str, task_data: Dict[str, Any], result: Dict[str, Any]):
        """Save agent results to file"""
        try:
            output_dir = Path("agent_results")
            output_dir.mkdir(exist_ok=True)
            
            result_file = output_dir / f"{agent_name}_{task_data.get('task_id', 'unknown')}.json"
            
            with open(result_file, 'w') as f:
                json.dump({
                    "agent": agent_name,
                    "task_data": task_data,
                    "result": result,
                    "timestamp": str(Path(result_file).stat().st_mtime)
                }, f, indent=2)
                
        except Exception as e:
            logger = logging.getLogger(f"callback.{agent_name}")
            logger.error(f"Failed to save results: {e}")


class PDFMainAgent(LlmAgent):
    """Main coordinator agent for PDF processing system"""
    
    def __init__(self):
        # Create sub-agents
        self.preprocessor = PDFPreProcessingAgent()
        self.postprocessor = PDFPostProcessingAgent()
        
        # Register tools with sub-agents
        self._register_tools()
        
        # Set up callbacks
        self._setup_callbacks()
        
        # Initialize main agent
        super().__init__(
            name="pdf_coordinator",
            model="gemini-2.0-flash-thinking",
            instruction="""You are the main coordinator for PDF processing. Your responsibilities:
            1. Orchestrate the entire PDF processing workflow
            2. Coordinate between preprocessing and postprocessing agents
            3. Handle error recovery and retry logic
            4. Ensure quality control throughout the process
            
            Always maintain clear communication with sub-agents and provide comprehensive reports.""",
            description="Coordinates PDF processing workflow between multiple specialized agents",
            sub_agents=[self.preprocessor, self.postprocessor]
        )
        
        self.logger = logging.getLogger(f"agent.{self.name}")
    
    def _register_tools(self):
        """Register PDF processing tools with sub-agents"""
        # Create tool instances
        validate_tool = Tool(
            name="validate_pdf",
            func=PDFTools.validate_pdf_file,
            description="Validates PDF file integrity and basic properties"
        )
        
        metadata_tool = Tool(
            name="extract_metadata", 
            func=PDFTools.extract_pdf_metadata,
            description="Extracts metadata from PDF files"
        )
        
        format_tool = Tool(
            name="format_results",
            func=PDFTools.format_extraction_results,
            description="Formats PDF extraction results"
        )
        
        # Register tools with agents
        self.preprocessor.tools = [validate_tool, metadata_tool]
        self.postprocessor.tools = [format_tool]
        
        self.logger.info("Registered tools with sub-agents")
    
    def _setup_callbacks(self):
        """Setup before and after callbacks for all agents"""
        agents = [self, self.preprocessor, self.postprocessor]
        
        for agent in agents:
            # Before callbacks
            agent.before_callbacks = [
                lambda agent, task: BeforeAgentCallback.log_start(agent.name, task),
                lambda agent, task: BeforeAgentCallback.validate_inputs(agent.name, task)
            ]
            
            # After callbacks  
            agent.after_callbacks = [
                lambda agent, task, result: AfterAgentCallback.log_completion(agent.name, task, result),
                lambda agent, task, result: AfterAgentCallback.save_results(agent.name, task, result)
            ]
            
        self.logger.info("Setup callbacks for all agents")
    
    def process_pdf(self, file_path: str, task_id: str = None) -> Dict[str, Any]:
        """Main method to process a PDF file through the multi-agent system"""
        try:
            if not task_id:
                import uuid
                task_id = str(uuid.uuid4())[:8]
            
            self.logger.info(f"Starting PDF processing pipeline for: {file_path}")
            
            # Task data for the workflow
            task_data = {
                "file_path": file_path,
                "task_id": task_id,
                "task_type": "pdf_processing"
            }
            
            # Step 1: Preprocessing
            self.logger.info("Step 1: Running preprocessing agent...")
            preprocess_result = self.preprocessor.run(
                input=f"Validate and prepare PDF file: {file_path}",
                context=task_data
            )
            
            if not preprocess_result.get("success", False):
                return {
                    "success": False,
                    "error": "Preprocessing failed",
                    "details": preprocess_result
                }
            
            # Step 2: Main Processing (placeholder - you'll add your logic here)
            self.logger.info("Step 2: Main PDF content extraction...")
            # This is where you'd integrate your actual PDF processing logic
            extraction_result = {
                "text": "Sample extracted text content...",
                "tables": [],
                "images": [],
                "success": True
            }
            
            # Step 3: Postprocessing
            self.logger.info("Step 3: Running postprocessing agent...")
            postprocess_result = self.postprocessor.run(
                input="Format and validate extracted PDF content",
                context={**task_data, "extraction_result": extraction_result}
            )
            
            # Final result
            final_result = {
                "success": True,
                "task_id": task_id,
                "file_path": file_path,
                "preprocessing": preprocess_result,
                "extraction": extraction_result,
                "postprocessing": postprocess_result
            }
            
            self.logger.info(f"PDF processing pipeline completed successfully: {task_id}")
            return final_result
            
        except Exception as e:
            self.logger.error(f"PDF processing pipeline failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "task_id": task_id,
                "file_path": file_path
            }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get status of the multi-agent system"""
        return {
            "main_agent": {
                "name": self.name,
                "model": self.model,
                "status": "active"
            },
            "sub_agents": [
                {
                    "name": agent.name,
                    "model": agent.model,
                    "tools": len(getattr(agent, 'tools', [])),
                    "status": "active"
                }
                for agent in [self.preprocessor, self.postprocessor]
            ],
            "callbacks_configured": {
                "before_callbacks": len(self.before_callbacks) if hasattr(self, 'before_callbacks') else 0,
                "after_callbacks": len(self.after_callbacks) if hasattr(self, 'after_callbacks') else 0
            }
        }


# Initialize the multi-agent system
def create_pdf_multiagent_system() -> PDFMainAgent:
    """Factory function to create and configure the PDF multi-agent system"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    system = PDFMainAgent()
    logging.getLogger("pdf_multiagent").info("PDF multi-agent system initialized successfully")
    
    return system


# Example usage
if __name__ == "__main__":
    # Create the multi-agent system
    pdf_system = create_pdf_multiagent_system()
    
    # Get system status
    status = pdf_system.get_system_status()
    print("System Status:", json.dumps(status, indent=2))
    
    # Process a PDF file (example)
    # result = pdf_system.process_pdf("/path/to/sample.pdf")
    # print("Processing Result:", json.dumps(result, indent=2))