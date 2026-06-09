import requests
import csv
import io

class Fetcher:
    def __init__(self, proxy_url=None):
        self.proxy_url = proxy_url  # например "https://alwex-vpn.vercel.app/proxy?url="
    
    def from_url(self, url, use_proxy=True, timeout=30):
        target = (self.proxy_url + url) if use_proxy else url
        resp = requests.get(target, timeout=timeout)
        resp.raise_for_status()
        return self._parse_csv(resp.text)
    
    def from_file(self, filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return self._parse_csv(f.read())
    
    def _parse_csv(self, data):
        lines = data.splitlines()
        # удаляем первые строки, начинающиеся с '#' или '*'
        filtered = [line for line in lines if line and not line.startswith('#') and not line.startswith('*')]
        reader = csv.reader(filtered)
        servers = []
        for row in reader:
            if len(row) >= 15:
                servers.append({
                    'ip': row[1],
                    'country': row[6],
                    'hostname': row[0],
                    'base64_config': row[14],  # 15-е поле
                })
        return servers