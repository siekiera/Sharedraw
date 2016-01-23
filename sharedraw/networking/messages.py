import base64
import json
import logging
import sys

from sharedraw.config import own_id


logger = logging.getLogger(__name__)


class Message:
    """
    Komunikat do wymiany danych z innymi użytkownikami
    """

    def to_json(self):
        pass

    def to_bytes(self):
        """ Konwertuje komunikat do JSON-a, a następnie do tablicy bajtów
        :return: tablica bajtów
        """
        jsondata = self.to_json()
        # Dla Bogdana
        jsondata += '\n'
        bytedata = bytes(jsondata, encoding='utf8')
        return bytedata


class PaintMessage(Message):
    """
    Komunikat służący do przesłania danych o obrazie
    """

    def __init__(self, changed_pxs: [], color: str):
        self.changed_pxs = changed_pxs
        self.color = color

    @staticmethod
    def from_json(msg: {}):
        if not msg['pointList']:
            logger.error('No coords!')
        changed_pxs = list(map(lambda coord_obj: (coord_obj['x'], coord_obj['y']), msg['pointList']))
        return PaintMessage(changed_pxs, 'white' if msg['color'] == '255' else 'black')

    def to_json(self):
        data = list(map(lambda xy: {'x': xy[0], 'y': xy[1]}, self.changed_pxs))
        msg = {
            'type': 'paint',
            'clientId': own_id,
            'pointList': data,
            # 'startLine': 'true',
            'color': '255' if self.color == 'white' else '0'
        }
        return json.dumps(msg)


class ImageMessage(Message):
    """ Komunikat zawierający aktualny stan tablicy po dołączeniu się klienta
    """

    def __init__(self, client_id: str, rawdata: bytes):
        self.client_id = client_id
        self.rawdata = rawdata

    @staticmethod
    def from_json(msg: {}):
        if not msg['clientId']:
            logger.error('No clientId!')
        if not msg['image']:
            logger.error('No image!')
        return ImageMessage(msg['clientId'], base64.b64decode(msg['image']))

    def to_json(self):
        # TODO: na razie brak obsługi danych obrazu, pobieramy tylko clientId
        msg = {
            'type': 'image',
            'clientId': self.client_id,
            'image': str(base64.b64encode(self.rawdata), encoding="utf8")
        }
        return json.dumps(msg)


class JoinMessage(Message):
    """ Komunikat potwiedzający dołączenie się klienta
    """

    def __init__(self, client_id: str):
        self.client_id = client_id
        # Wewnętrzny przełącznik - czy klientowi należy odesłać ImageMessage
        self.send_back_img = False

    @staticmethod
    def from_json(msg: {}):
        if not msg['clientId']:
            logger.error('No clientId!')
        return JoinMessage(msg['clientId'])

    def to_json(self):
        msg = {
            'type': 'joined',
            'clientId': self.client_id
        }
        return json.dumps(msg)


class QuitMessage(Message):
    """ Komunikat potwiedzający odłączenie się klienta
    """

    def __init__(self, client_id: str):
        self.client_id = client_id

    @staticmethod
    def from_json(msg: {}):
        if not msg['clientId']:
            logger.error('No clientId!')
        return QuitMessage(msg['clientId'])

    def to_json(self):
        msg = {
            'type': 'quit',
            'clientId': self.client_id
        }
        return json.dumps(msg)


class KeepAliveMessage(Message):
    """ Komunikat potwierdzający aktywność klienta
    """

    def __init__(self, client_id: str):
        self.client_id = client_id

    @staticmethod
    def from_json(msg: {}):
        if not msg['clientId']:
            logger.error('No clientId!')
        return KeepAliveMessage(msg['clientId'])

    def to_json(self):
        msg = {
            'type': 'keepAlive',
            'clientId': self.client_id
        }
        return json.dumps(msg)


class CleanMessage(Message):
    """ Komunikat zlecający wyczyszczenie tablicy
    """

    def __init__(self, client_id: str):
        self.client_id = client_id

    @staticmethod
    def from_json(msg: {}):
        if not msg['clientId']:
            logger.error('No clientId!')
        return CleanMessage(msg['clientId'])

    def to_json(self):
        msg = {
            'type': 'clean',
            'clientId': self.client_id
        }
        return json.dumps(msg)

message_type_handlers = {
    'paint': PaintMessage.from_json,
    'joined': JoinMessage.from_json,
    'image': ImageMessage.from_json,
    'keepAlive': KeepAliveMessage.from_json,
    'quit': QuitMessage.from_json,
    'clean': CleanMessage.from_json
}


def from_json(jsonstr: str):
    try:
        data = json.loads(jsonstr)
        # if len(data) != 1:
        if not data['type']:
            logger.error("Nieprawidłowy komunikat!")
            return
        # Element type - typ komunikatu
        message_type = data['type']
        h = message_type_handlers.get(message_type)
        if not h:
            logger.error("Nieznany typ komunikatu: %s" % message_type)
        # Wywołanie funkcji obsługującej: f(jsonobj)
        return h(data)
    except (ValueError, KeyError):
        logger.error("Cannot decode: %s, error: %s" % (jsonstr, sys.exc_info()))
        return None


class SignedMessage:
    """ Podpisany komunikat (z autorem)
    """

    def __init__(self, client_id: str, message: Message):
        self.client_id = client_id
        self.message = message
