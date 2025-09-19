"""
Mock Email Server for Local Testing
Simulates Microsoft Graph API responses without requiring real Azure credentials
"""

import json
import time
import uuid
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import threading
import random
from flask import Flask, jsonify, request, send_file
import io

class MockEmailServer:
    """Mock server that simulates Microsoft Graph API responses"""
    
    def __init__(self, port: int = 5001):
        self.port = port
        self.app = Flask(__name__)
        self.messages = []
        self.delta_tokens = {}
        self.attachment_data = {}
        
        # Generate dummy messages with attachments
        self._generate_dummy_messages()
        self._setup_routes()
        
    def _generate_dummy_messages(self):
        """Generate realistic dummy email messages with attachments"""
        senders = [
            "finance@company.com",
            "reports@analytics.com", 
            "notifications@system.com",
            "admin@testdomain.com"
        ]
        
        subjects = [
            "Monthly Financial Report",
            "System Performance Analysis",
            "Weekly Data Summary",
            "Compliance Documentation",
            "Budget Review Results"
        ]
        
        # Generate sample PDF content
        sample_pdf = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n72 720 Td\n(Test Document) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000206 00000 n \ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n299\n%%EOF'
        
        # Generate dummy Excel-like content (simple CSV)
        sample_excel = b'Name,Value,Date\nTest Item 1,100,2024-01-01\nTest Item 2,200,2024-01-02\nTest Item 3,300,2024-01-03'
        
        # Generate messages
        for i in range(20):
            message_id = str(uuid.uuid4())
            sender = random.choice(senders)
            subject = f"{random.choice(subjects)} - {datetime.now().strftime('%Y-%m-%d')}"
            
            # Create attachments
            attachments = []
            num_attachments = random.randint(1, 3)
            
            for j in range(num_attachments):
                attachment_id = str(uuid.uuid4())
                if j % 2 == 0:
                    # PDF attachment
                    filename = f"report_{i}_{j}.pdf"
                    content = sample_pdf
                    content_type = "application/pdf"
                else:
                    # Excel attachment
                    filename = f"data_{i}_{j}.xlsx"
                    content = sample_excel
                    content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                
                # Store attachment data
                self.attachment_data[f"{message_id}_{attachment_id}"] = content
                
                attachments.append({
                    "id": attachment_id,
                    "name": filename,
                    "contentType": content_type,
                    "size": len(content),
                    "isInline": False
                })
            
            message = {
                "id": message_id,
                "subject": subject,
                "from": {
                    "emailAddress": {
                        "address": sender,
                        "name": sender.split('@')[0].title()
                    }
                },
                "receivedDateTime": (datetime.now() - timedelta(minutes=random.randint(1, 1440))).isoformat() + "Z",
                "hasAttachments": len(attachments) > 0,
                "attachments": attachments,
                "body": {
                    "content": f"This is a test email with {len(attachments)} attachments for testing purposes.",
                    "contentType": "text"
                }
            }
            
            self.messages.append(message)
    
    def _setup_routes(self):
        """Setup Flask routes to mimic Graph API endpoints"""
        
        @self.app.route('/v1.0/oauth2/v2.0/token', methods=['POST'])
        def get_token():
            """Mock authentication endpoint"""
            return jsonify({
                "access_token": "mock_access_token_12345",
                "token_type": "Bearer",
                "expires_in": 3600
            })
        
        @self.app.route('/v1.0/me/messages/delta', methods=['GET'])
        def get_messages_delta():
            """Mock delta query endpoint"""
            # Simulate returning some messages
            delta_token = request.args.get('$deltatoken')
            
            if not delta_token:
                # First request - return some messages
                messages_subset = self.messages[:random.randint(1, 5)]
                new_delta_token = str(uuid.uuid4())
                
                return jsonify({
                    "value": messages_subset,
                    "@odata.deltaLink": f"http://localhost:{self.port}/v1.0/me/messages/delta?$deltatoken={new_delta_token}"
                })
            else:
                # Subsequent request - return fewer or no new messages
                if random.random() < 0.3:  # 30% chance of new messages
                    new_messages = self.messages[random.randint(0, min(3, len(self.messages)-1)):]
                    new_delta_token = str(uuid.uuid4())
                    
                    return jsonify({
                        "value": new_messages[:random.randint(0, 2)],
                        "@odata.deltaLink": f"http://localhost:{self.port}/v1.0/me/messages/delta?$deltatoken={new_delta_token}"
                    })
                else:
                    # No new messages
                    return jsonify({
                        "value": [],
                        "@odata.deltaLink": f"http://localhost:{self.port}/v1.0/me/messages/delta?$deltatoken={delta_token}"
                    })
        
        @self.app.route('/v1.0/me/messages/<message_id>/attachments', methods=['GET'])
        def get_attachments(message_id):
            """Mock attachments endpoint"""
            # Find message
            message = next((m for m in self.messages if m['id'] == message_id), None)
            if not message:
                return jsonify({"error": "Message not found"}), 404
            
            return jsonify({
                "value": message.get('attachments', [])
            })
        
        @self.app.route('/v1.0/me/messages/<message_id>/attachments/<attachment_id>/$value', methods=['GET'])
        def download_attachment(message_id, attachment_id):
            """Mock attachment download endpoint"""
            attachment_key = f"{message_id}_{attachment_id}"
            
            if attachment_key not in self.attachment_data:
                return jsonify({"error": "Attachment not found"}), 404
            
            content = self.attachment_data[attachment_key]
            return send_file(
                io.BytesIO(content),
                as_attachment=True,
                download_name=f"attachment_{attachment_id}",
                mimetype='application/octet-stream'
            )
        
        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Health check endpoint"""
            return jsonify({
                "status": "healthy",
                "messages_count": len(self.messages),
                "timestamp": datetime.now().isoformat()
            })
    
    def start_server(self):
        """Start the mock server in a separate thread"""
        def run_server():
            self.app.run(
                host='0.0.0.0',
                port=self.port,
                debug=False,
                use_reloader=False,
                threaded=True
            )
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        # Wait a bit for server to start
        time.sleep(2)
        print(f"🚀 Mock email server started at http://localhost:{self.port}")
        print(f"   Health check: http://localhost:{self.port}/health")
        print(f"   Generated {len(self.messages)} dummy messages")
        
        return server_thread

def main():
    """Run the mock server standalone"""
    server = MockEmailServer()
    server.start_server()
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Mock server stopped")

if __name__ == "__main__":
    main()