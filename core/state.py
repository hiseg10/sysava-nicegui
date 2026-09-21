"""
Estado compartilhado do SysAVA (evita imports circulares).

sync_pronta: threading.Event que sinaliza quando o sync inicial terminou.
"""
import threading

sync_pronta = threading.Event()
