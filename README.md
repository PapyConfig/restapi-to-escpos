# 🖨️ Thermal Printer API

REST API for sending **ESC/POS** commands to thermal receipt printers over the network.

---

## 📋 Features
- Network printing (TCP/IP) via ESC/POS protocol  
- Support for most ESC/POS printer commands  
- RESTful API with **FastAPI**  
- Docker container support  
- Public Docker image on GitHub Container Registry  
- Environment variable configuration  
- CI/CD with GitHub Actions  

---

## 🚀 Quick Start

### Using Docker (Recommended)
```bash
# Pull and run the latest image
docker run -d   --name thermal-printer-api   -p 8000:8000   -e PRINTER_IP=192.168.1.100   -e PRINTER_PORT=9100   ghcr.io/papyconfig/restapi-to-escpos:latest
```

### Using Docker Compose
Create a `docker-compose.yml` file:
```yaml
version: '3.8'

services:
  thermal-printer-api:
    image: ghcr.io/papyconfig/restapi-to-escpos:latest
    container_name: thermal-printer-api
    ports:
      - "8000:8000"
    environment:
      - PRINTER_IP=192.168.1.100
      - PRINTER_PORT=9100
    restart: unless-stopped
```

Run with:
```bash
docker-compose up -d
```

### Local Installation with Python
```bash
# Clone the repository
git clone https://github.com/papyconfig/restapi-to-escpos.git
cd restapi-to-escpos

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export PRINTER_IP=192.168.1.100
export PRINTER_PORT=9100

# Run the application
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 🎯 API Usage

### Main Endpoint
```http
POST /print
```

#### Basic Print Request
```json
{
  "commands": [
    {"align": "center"},
    {"bold": true},
    {"text": "HELLO WORLD\n"},
    {"cut": "PART"}
  ]
}
```

#### Advanced Print Request
```json
{
  "commands": [
    {"align": "center"},
    {"bold": true},
    {"text": "STORE RECEIPT\n"},
    {"text": "================\n"},
    {"align": "left"},
    {"bold": false},
    {"text": "Item 1        10.00€\n"},
    {"text": "Item 2        15.50€\n"},
    {"text": "================\n"},
    {"align": "right"},
    {"bold": true},
    {"text": "TOTAL:       25.50€\n"},
    {"qr": "https://example.com/receipt/123, size=3, ec=0"},
    {"barcode": "123456789012, bc=CODE128, height=64, width=3"},
    {"cut": "PART"}
  ]
}
```

---

## 📡 API Endpoints

| Endpoint        | Method | Description                 |
|-----------------|--------|-----------------------------|
| `/`             | GET    | API homepage with info      |
| `/health`       | GET    | Health check                |
| `/print`        | POST   | Main printing endpoint      |
| `/jobs/{job_id}`| GET    | Get print job status        |
| `/examples`     | GET    | Get command examples        |

---

## ⚙️ Environment Variables

| Variable     | Description            | Default Value   |
|--------------|------------------------|-----------------|
| `PRINTER_IP` | Default printer IP     | `192.168.1.100` |
| `PRINTER_PORT` | Default printer port | `9100`          |

---

## 📚 Supported ESC/POS Commands

### Text Formatting
```json
{"text": "Hello World\n"}
{"align": "center"}
{"bold": true}
{"underline": 1}
{"font": "a"}
{"size": "2h"}
```

### QR Code
```json
{"qr": "https://example.com, size=4, ec=0"}
{"qr": "Hello World, size=3, model=2, ec=1"}
```

### Barcode
```json
{"barcode": "123456789012, bc=EAN13, height=64, width=3"}
{"barcode": "ABC123, bc=CODE128, pos=BELOW, font=A"}
```

### Image
```json
{"image": "/path/to/image.png"}
```

### Printer Control
```json
{"cut": "PART"}
{"cut": "FULL"}
{"cashdraw": 2}
{"feed": 3}
{"lf": ""}
{"hw": "INIT"}
{"control": "LF"}
```

### Advanced Formatting
```json
{"set": {"align": "center", "bold": true, "font": "a"}}
{"set_line_spacing": 40}
{"set_barcode_height": 70}
{"set_barcode_width": 3}
```

---

## 📝 Complete Examples

### Simple Receipt
```bash
curl -X POST "http://localhost:8000/print"   -H "Content-Type: application/json"   -d '{
    "commands": [
      {"align": "center"},
      {"bold": true},
      {"text": "WELCOME!\n"},
      {"text": "================\n"},
      {"align": "left"},
      {"bold": false},
      {"text": "Coffee          2.50€\n"},
      {"text": "Croissant       1.80€\n"},
      {"text": "================\n"},
      {"align": "right"},
      {"bold": true},
      {"text": "TOTAL:        4.30€\n"},
      {"cut": "PART"}
    ]
  }'
```

### Receipt with QR Code & Barcode
```bash
curl -X POST "http://localhost:8000/print"   -H "Content-Type: application/json"   -d '{
    "commands": [
      {"align": "center"},
      {"bold": true},
      {"text": "STORE RECEIPT\n"},
      {"text": "================\n"},
      {"align": "left"},
      {"text": "Item: T-Shirt\n"},
      {"text": "Price: 19.99€\n"},
      {"qr": "https://store.com/item/123, size=3"},
      {"barcode": "123456789012, bc=CODE128"},
      {"cut": "FULL"}
    ]
  }'
```

### Custom Formatting
```bash
curl -X POST "http://localhost:8000/print"   -H "Content-Type: application/json"   -d '{
    "commands": [
      {"set": {"align": "center", "bold": true, "size": "2h"}},
      {"text": "IMPORTANT\n"},
      {"set": {"align": "left", "bold": false, "size": "normal"}},
      {"text": "This is normal text\n"},
      {"set": {"underline": 1}},
      {"text": "Underlined text\n"},
      {"set": {"underline": 0}},
      {"cut": "PART"}
    ]
  }'
```

---

## 📄 License
**MIT License** – See [LICENSE](./LICENSE) for details.  
If you use this code, please provide attribution to the original repository.

---

## 🤝 Contributing
- Fork the repository  
- Create a feature branch  
- Commit your changes  
- Push to the branch  
- Open a Pull Request  

---

> Built with ❤️ for the open-source community
