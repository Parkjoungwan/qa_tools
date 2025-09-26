import http.server
import socketserver

PORT = 8000

Handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"서버가 http://localhost:{PORT} 에서 실행 중입니다.")
    print(f"웹 브라우저에서 http://localhost:{PORT}/hichord.html 주소를 여세요.")
    httpd.serve_forever()
