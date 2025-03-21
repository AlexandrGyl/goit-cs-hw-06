import socket
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import mimetypes
import pathlib
import multiprocessing
from datetime import datetime
from pymongo import MongoClient
import os
from dotenv import load_dotenv


load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')
if not MONGO_URI:
    raise ValueError("MONGO_URI is not set in the environment variables.")


class HttpHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            
            data = self.rfile.read(int(self.headers['Content-Length']))
            data_parse = urllib.parse.unquote_plus(data.decode())
            data_dict = {key: value for key, value in [el.split('=') for el in data_parse.split('&')]}

            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect(('localhost', 5000))  
                json_data = json.dumps(data_dict)
                sock.sendall(json_data.encode())

            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()

        except Exception as e:
            print(f"Error during POST: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'Internal Server Error')

    def do_GET(self):
        try:
            pr_url = urllib.parse.urlparse(self.path)
            if pr_url.path == '/':
                self.send_html_file('web_data/index.html')
            elif pr_url.path == '/message':
                self.send_html_file('web_data/message.html')
            else:
                if pathlib.Path().joinpath('web_data', pr_url.path[1:]).exists():
                    self.send_static(pr_url.path[1:])
                else:
                    self.send_html_file('web_data/error.html', 404)

        except Exception as e:
            print(f"Error during GET: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'Internal Server Error')

    def send_html_file(self, filename, status=200):
        try:
            self.send_response(status)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open(filename, 'rb') as fd:
                self.wfile.write(fd.read())
        except Exception as e:
            print(f"Error sending HTML file: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'Error sending HTML file')

    def send_static(self, filename):
        try:
            file_path = pathlib.Path('web_data') / filename
            mime_type, _ = mimetypes.guess_type(file_path)
            mime_type = mime_type if mime_type else 'application/octet-stream'

            self.send_response(200)
            self.send_header("Content-type", mime_type)
            self.end_headers()

            with open(file_path, 'rb') as file:
                self.wfile.write(file.read())

        except Exception as e:
            print(f"Error sending static file: {e}")
            self.send_response(404)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'File not found')


def run_socket():
    try:
        client = MongoClient(MONGO_URI)
        db = client.messages_db
        collection = db.messages

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind(('0.0.0.0', 5000))
            server_socket.listen()
            print("Socket Server running on port 5000")

            while True:
                conn, addr = server_socket.accept()
                with conn:
                    data = conn.recv(1024)
                    if data:
                        try:
                            msg_dict = json.loads(data.decode())
                            msg_dict['date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                            collection.insert_one(msg_dict)
                            print("Saved to MongoDB:", msg_dict)
                        except json.JSONDecodeError:
                            print("Received invalid JSON data")
                            conn.sendall(b"Invalid data format")
                        except Exception as e:
                            print(f"Error saving message: {e}")
                            conn.sendall(b"Error saving message")

    except Exception as e:
        print(f"Error in Socket Server: {e}")

# === HTTP-сервер ===
def run_http():
    server_address = ('', 3000)
    http = HTTPServer(server_address, HttpHandler)
    print("HTTP Server running on port 3000")
    http.serve_forever()

if __name__ == '__main__':
    # Стартуємо HTTP-сервер та Socket-сервер в окремих процесах
    p1 = multiprocessing.Process(target=run_http)
    p2 = multiprocessing.Process(target=run_socket)
    p1.start()
    p2.start()
    p1.join()
    p2.join()
