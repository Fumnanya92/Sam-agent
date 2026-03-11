import sys
sys.path.insert(0, ".")
from skills.flutter_tester import _dart_ports, _find_flutter_url

ports = _dart_ports()
print("Dart ports found:", ports)
url = _find_flutter_url(None)
print("Flutter URL:", url)
