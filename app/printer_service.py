import logging
from escpos.printer import Network
from typing import List, Dict, Any
import requests
import os
import tempfile

logger = logging.getLogger(__name__)

class ThermalPrinterService:
    def __init__(self, profile: str = 'NT-80-V-UL'):
        self.printer = None
        self.profile = profile
    
    def connect_printer(self, ip: str, port: int = 9100) -> bool:
        """Établit la connexion avec l'imprimante thermique"""
        try:
            # Toujours fermer une connexion existante
            if self.printer:
                try:
                    self.printer.close()
                except:
                    pass
            
            self.printer = Network(ip, port, timeout=30, profile=self.profile)
            return True
        except Exception as e:
            logger.error(f"Erreur de connexion à l'imprimante {ip}:{port} - {str(e)}")
            self.printer = None
            return False
    
    def disconnect_printer(self):
        """Déconnecte l'imprimante"""
        if self.printer:
            try:
                # Envoyer un flush avant de fermer
                self.printer._raw(b'\x0c')  # Form feed
                self.printer.close()
            except Exception as e:
                logger.error(f"Erreur lors de la déconnexion: {str(e)}")
            finally:
                self.printer = None
    
    def download_image(self, url: str) -> str:
        """Télécharge une image depuis une URL et la sauve temporairement"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Créer un fichier temporaire
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_file.write(response.content)
            temp_file.close()
            
            return temp_file.name
        except Exception as e:
            logger.error(f"Erreur de téléchargement de l'image {url}: {str(e)}")
            raise
    
    def parse_complex_params(self, value: str) -> dict:
        """Parse les paramètres complexes depuis une chaîne"""
        params = {}
        parts = value.split(', ')
        
        if len(parts) > 0:
            params['content'] = parts[0].strip()
            
            for part in parts[1:]:
                if '=' in part:
                    key_value = part.split('=', 1)
                    if len(key_value) == 2:
                        key, value_str = key_value
                        key = key.strip()
                        value_str = value_str.strip()
                        
                        if value_str.lower() in ['true', 'false']:
                            params[key] = value_str.lower() == 'true'
                        elif value_str.isdigit():
                            params[key] = int(value_str)
                        elif value_str.startswith("'") and value_str.endswith("'"):
                            params[key] = value_str[1:-1]
                        elif value_str.startswith('"') and value_str.endswith('"'):
                            params[key] = value_str[1:-1]
                        else:
                            params[key] = value_str
        
        if 'content' not in params:
            params['content'] = value.strip()
        return params
    
    def execute_command(self, command: Dict[str, Any]):
        """Exécute une commande ESC/POS"""
        if not self.printer:
            raise Exception("Imprimante non connectée")
        
        try:
            for esc_pos_cmd, value in command.items():
                cmd = esc_pos_cmd.lower()
                
                if cmd == "text":
                    self.printer.text(str(value))
                elif cmd == "qr":
                    if isinstance(value, str) and ', ' in value:
                        qr_params = self.parse_complex_params(value)
                        content = qr_params.get('content', str(value))
                        size = qr_params.get('size', 3)
                        ec = qr_params.get('ec', 0)
                        model = qr_params.get('model', 2)
                        native = qr_params.get('native', False)
                        center = qr_params.get('center', False)
                        self.printer.qr(content, size=size, ec=ec, model=model, native=native, center=center)
                    else:
                        self.printer.qr(str(value))
                elif cmd == "barcode":
                    if isinstance(value, str) and ', ' in value:
                        bc_params = self.parse_complex_params(value)
                        content = bc_params.get('content', str(value))
                        bc = bc_params.get('bc', 'CODE128')
                        height = bc_params.get('height', 64)
                        width = bc_params.get('width', 3)
                        pos = bc_params.get('pos', 'BELOW')
                        font = bc_params.get('font', 'A')
                        align_ct = bc_params.get('align_ct', True)
                        function_type = bc_params.get('function_type', None)
                        check = bc_params.get('check', True)
                        force_software = bc_params.get('force_software', False)
                        self.printer.barcode(content, bc, height=height, width=width, pos=pos, 
                                           font=font, align_ct=align_ct, function_type=function_type,
                                           check=check, force_software=force_software)
                    else:
                        self.printer.barcode(str(value), 'CODE128')
                elif cmd == "image":
                    temp_file = None
                    try:
                        if isinstance(value, str):
                            if value.startswith('http://') or value.startswith('https://'):
                                # Télécharger l'image depuis l'URL
                                temp_file = self.download_image(value)
                                image_path = temp_file
                            elif ', ' in value:
                                # Parser les paramètres image
                                img_params = self.parse_complex_params(value)
                                image_path = img_params.get('content', str(value))
                                
                                # Extraire les paramètres spécifiques à l'image
                                high_density_vertical = img_params.get('high_density_vertical', True)
                                high_density_horizontal = img_params.get('high_density_horizontal', True)
                                impl = img_params.get('impl', 'bitImageRaster')
                                fragment_height = img_params.get('fragment_height', 960)
                                center = img_params.get('center', False)
                                
                                self.printer.image(
                                    image_path,
                                    high_density_vertical=high_density_vertical,
                                    high_density_horizontal=high_density_horizontal,
                                    impl=impl,
                                    fragment_height=fragment_height,
                                    center=center
                                )
                                return  # Image already printed, exit early
                            else:
                                image_path = str(value)
                            
                            # Image sans paramètres spécifiques
                            self.printer.image(image_path)
                        else:
                            self.printer.image(str(value))
                    finally:
                        # Nettoyer le fichier temporaire si nécessaire
                        if temp_file and os.path.exists(temp_file):
                            try:
                                os.unlink(temp_file)
                            except:
                                pass
                elif cmd == "cut":
                    mode = value if isinstance(value, str) else "PART"
                    # Ajouter quelques lignes avant le cut pour s'assurer que l'image est imprimée
                    self.printer._raw(b'\n\n')
                    self.printer.cut(mode)
                    # Forcer l'impression immédiate
                    self.printer._raw(b'\x0c')  # Form feed
                elif cmd == "cashdraw":
                    pin = value if isinstance(value, int) else 2
                    self.printer.cashdraw(pin)
                elif cmd == "set":
                    if isinstance(value, dict):
                        self.printer.set(**value)
                elif cmd == "hw":
                    self.printer.hw(str(value))
                elif cmd == "control":
                    self.printer.control(str(value))
                elif cmd == "feed":
                    n = value if isinstance(value, int) else 1
                    self.printer.feed(n)
                elif cmd == "lf":
                    self.printer.lf()
                elif cmd == "set_text":
                    self.printer.set_text(str(value))
                elif cmd == "set_font":
                    self.printer.set_font(str(value))
                elif cmd == "set_align":
                    self.printer.set_align(str(value))
                elif cmd == "set_bold":
                    bold = value if isinstance(value, bool) else bool(value)
                    self.printer.set_bold(bold)
                elif cmd == "set_underline":
                    underline = value if isinstance(value, (int, bool)) else 1
                    self.printer.set_underline(underline)
                elif cmd == "set_size":
                    size = value if isinstance(value, str) else "normal"
                    self.printer.set_size(size)
                elif cmd == "set_height":
                    height = value if isinstance(value, int) else 1
                    self.printer.set_height(height)
                elif cmd == "set_width":
                    width = value if isinstance(value, int) else 1
                    self.printer.set_width(width)
                elif cmd == "set_justification":
                    self.printer.set_justification(str(value))
                elif cmd == "set_line_spacing":
                    spacing = value if isinstance(value, int) else 30
                    self.printer.set_line_spacing(spacing)
                elif cmd == "set_barcode_height":
                    height = value if isinstance(value, int) else 50
                    self.printer.set_barcode_height(height)
                elif cmd == "set_barcode_width":
                    width = value if isinstance(value, int) else 2
                    self.printer.set_barcode_width(width)
                elif cmd == "align":
                    self.printer.set(align=str(value))
                elif cmd == "bold":
                    bold = value if isinstance(value, bool) else bool(value)
                    self.printer.set(bold=bold)
                elif cmd == "underline":
                    underline = value if isinstance(value, (int, bool)) else 1
                    self.printer.set(underline=underline)
                elif cmd == "font":
                    self.printer.set(font=str(value))
                elif cmd == "size":
                    size = value if isinstance(value, str) else "normal"
                    self.printer.set(size=size)
                else:
                    logger.warning(f"Commande non reconnue: {cmd}")
                
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de la commande {esc_pos_cmd}: {str(e)}")
            raise
    
    def print_job(self, printer_ip: str, printer_port: int, commands: List[Dict[str, Any]], encoding: str = "utf-8") -> bool:
        """Exécute un job d'impression complet"""
        connection_success = False
        try:
            # Établir la connexion
            connection_success = self.connect_printer(printer_ip, printer_port)
            if not connection_success:
                raise Exception("Impossible de se connecter à l'imprimante")
            
            # Configuration de l'encodage
            self.printer._raw(bytes(f'\x1b\x74\x10', 'utf-8'))  # UTF-8
            self.printer._raw(b'\x1b\x40')  # Initialize printer
            
            # Exécution des commandes
            for command in commands:
                self.execute_command(command)
            
            # Forcer l'impression finale
            self.printer._raw(b'\n\n')
            self.printer._raw(b'\x0c')  # Form feed final
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur d'impression: {str(e)}")
            raise
        finally:
            # Toujours déconnecter
            try:
                self.disconnect_printer()
            except:
                pass
