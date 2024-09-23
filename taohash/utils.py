import netaddr


def ip_to_int(ip: str) -> int:
    return int(netaddr.IPAddress(ip))


def ip_version(ip: str) -> int:
    return netaddr.IPAddress(ip).version
