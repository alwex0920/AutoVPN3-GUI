# AutoVPN3-GUI

A cross-platform graphical frontend for the original `autovpn3.sh` script, allowing you to easily find and connect to free VPN Gate servers.

## Features
- Fetch server list from VPN Gate (via proxy or local file)
- Filter by country
- Test ping (ICMP or TCP) to find the fastest server
- Connect with custom protocol (TCP/UDP) and port
- Optional username/password authentication
- Real-time OpenVPN log viewer
- System tray integration
- Auto-start option

## Credits
This GUI is based on the original **autovpn3.sh** script by **MiAl** (https://miloserdov.org/?p=5858).  
The original script downloads server lists from vpngate.net, tests ping, and launches OpenVPN.  
This version adds a full GUI, proxy support, server management, and cross-platform packaging.

## Requirements
- Python 3.10+
- PyQt6
- fping (Linux) or ping (Windows)
- OpenVPN installed and in PATH
- Optional: tcping for TCP ping mode

## Installation & Usage
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `python main.py`
4. Build executable: `pyinstaller --onefile --windowed main.py`

## License
MIT

> **Note:** Code comments are written in Russian.
