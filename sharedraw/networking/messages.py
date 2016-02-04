import base64
import json
import logging
import sys
from collections import namedtuple

from sharedraw.config import own_id


logger = logging.getLogger(__name__)

TYPE = 'type'
CLIENT_ID = 'clientId'
POINT_LIST = 'pointList'
IMAGE = 'image'
COLOR = 'color'
DEST_CLIENT_ID = 'destClientId'
LAST_REQ_TIME = 'lastRequestLogicalTime'
LAST_BLOCK_TIME = 'lastBlockadeLogicalTime'
RICART_TABLE = 'ricartTable'
LOG_TIME = 'logicalTime'
TOKEN = 'token'
HAS_LOCK = 'hasLock'
CLIENT_LIST = 'clientList'
DETECTED_BY = 'detectedBy'
X = 'x'
Y = 'y'
COLOR_WHITE = 255
COLOR_BLACK = 0

PAINT_TYPE = 'paint'
IMAGE_TYPE = 'image'
JOIN_TYPE = 'joined'
QUIT_TYPE = 'quit'
KEEP_ALIVE_TYPE = 'keepAlive'
CLEAN_TYPE = 'clean'
REQUEST_TYPE = 'request'
RESIGN_TYPE = 'unlock'
PASS_TOKEN_TYPE = 'passToken'


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
        if not msg[POINT_LIST]:
            logger.error('No coords!')
        changed_pxs = list(map(lambda coord_obj: (coord_obj[X], coord_obj[Y]), msg[POINT_LIST]))
        return PaintMessage(changed_pxs, 'white' if COLOR in msg and msg[COLOR] == COLOR_WHITE else 'black')

    def to_json(self):
        data = list(map(lambda xy: {X: xy[0], Y: xy[1]}, self.changed_pxs))
        msg = {
            TYPE: PAINT_TYPE,
            CLIENT_ID: own_id,
            POINT_LIST: data,
            COLOR: COLOR_WHITE if self.color == 'white' else COLOR_BLACK
        }
        return json.dumps(msg)


class ImageMessage(Message):
    """ Komunikat zawierający aktualny stan tablicy po dołączeniu się klienta
    """

    def __init__(self, client_id: str, rawdata: bytes, client_ids: [], token_owner: str, locked: bool):
        self.client_id = client_id
        self.rawdata = rawdata
        self.client_ids = client_ids
        self.token_owner = token_owner
        self.locked = locked

    @staticmethod
    def from_json(msg: {}):
        if not msg[CLIENT_ID]:
            logger.error('No clientId!')
        if not msg[IMAGE]:
            logger.error('No image!')
        token_node = msg[TOKEN]
        return ImageMessage(msg[CLIENT_ID], base64.b64decode(msg[IMAGE]), msg[CLIENT_LIST], token_node[CLIENT_ID],
                            token_node[HAS_LOCK])

    def to_json(self):
        msg = {
            TYPE: IMAGE,
            CLIENT_ID: self.client_id,
            'clientList': self.client_ids,
            IMAGE: str(base64.b64encode(self.rawdata), encoding="utf8"),
            TOKEN: {
                CLIENT_ID: self.token_owner,
                HAS_LOCK: self.locked
            }
        }
        return json.dumps(msg)


class JoinMessage(Message):
    """ Komunikat potwiedzający dołączenie się klienta
    """

    def __init__(self, client_id: str):
        self.client_id = client_id
        # Wewnętrzne pole - od kogo dostaliśmy
        # None, jeśli od niego samego - oznacza, że klientowi należy odesłać ImageMessage
        self.received_from_id = False
        # Adres
        self.address = None

    @staticmethod
    def from_json(msg: {}):
        if not msg[CLIENT_ID]:
            logger.error('No clientId!')
        return JoinMessage(msg[CLIENT_ID])

    def to_json(self):
        msg = {
            TYPE: JOIN_TYPE,
            CLIENT_ID: self.client_id
        }
        return json.dumps(msg)


class QuitMessage(Message):
    """ Komunikat potwiedzający odłączenie się klienta
    """

    def __init__(self, client_ids: [], detected_by: str):
        self.client_ids = client_ids
        self.detected_by = detected_by

    @staticmethod
    def from_json(msg: {}):
        return QuitMessage(msg[CLIENT_LIST], msg[DETECTED_BY])

    def to_json(self):
        msg = {
            TYPE: QUIT_TYPE,
            CLIENT_LIST: self.client_ids,
            DETECTED_BY: self.detected_by
        }
        return json.dumps(msg)


class RequestTableMessage(Message):
    """ Żądanie przejęcia tablicy na własność
    """

    def __init__(self, client_id: str, logical_time: int):
        self.client_id = client_id
        self.logical_time = logical_time

    @staticmethod
    def from_json(msg: {}):
        return RequestTableMessage(msg[CLIENT_ID], int(msg[LOG_TIME]))

    def to_json(self):
        msg = {
            TYPE: REQUEST_TYPE,
            CLIENT_ID: self.client_id,
            LOG_TIME: self.logical_time
        }
        return json.dumps(msg)


class ResignMessage(Message):
    """ Komunikat informujący o rezygnacji z posiadania tablicy
    """

    def __init__(self, client_id: str):
        self.client_id = client_id

    @staticmethod
    def from_json(msg: {}):
        return ResignMessage(msg[CLIENT_ID])

    def to_json(self):
        msg = {
            TYPE: RESIGN_TYPE,
            CLIENT_ID: self.client_id,
        }
        return json.dumps(msg)


class PassTokenMessage(Message):
    """ Komunikat informujący o przekazaniu tokena (własności tablicy)
    """

    def __init__(self, dest_client_id: str, ricart_table: []):
        self.dest_client_id = dest_client_id
        self.ricart_table = ricart_table

    @staticmethod
    def from_json(msg: {}):
        rt = list(map(dict_to_rtr, msg[RICART_TABLE]))
        return PassTokenMessage(msg[DEST_CLIENT_ID], rt)

    def to_json(self):
        rt_dict = list(map(rtr_to_dict, self.ricart_table))
        msg = {
            TYPE: PASS_TOKEN_TYPE,
            DEST_CLIENT_ID: self.dest_client_id,
            RICART_TABLE: rt_dict
        }
        return json.dumps(msg)


RicartTableRow = namedtuple('RicartTableRow', 'id g r')


def rtr_to_dict(rtr: RicartTableRow):
    return {
        CLIENT_ID: rtr.id,
        LAST_REQ_TIME: rtr.r,
        LAST_BLOCK_TIME: rtr.g
    }


def dict_to_rtr(d: {}):
    return RicartTableRow(d[CLIENT_ID], d[LAST_BLOCK_TIME], d[LAST_REQ_TIME])


class CleanMessage(Message):
    """ Komunikat zlecający wyczyszczenie tablicy
    """

    def __init__(self, client_id: str):
        self.client_id = client_id

    @staticmethod
    def from_json(msg: {}):
        if not msg[CLIENT_ID]:
            logger.error('No clientId!')
        return CleanMessage(msg[CLIENT_ID])

    def to_json(self):
        msg = {
            TYPE: CLEAN_TYPE,
            CLIENT_ID: self.client_id
        }
        return json.dumps(msg)


message_type_handlers = {
    PAINT_TYPE: PaintMessage.from_json,
    JOIN_TYPE: JoinMessage.from_json,
    IMAGE_TYPE: ImageMessage.from_json,
    QUIT_TYPE: QuitMessage.from_json,
    CLEAN_TYPE: CleanMessage.from_json,
    REQUEST_TYPE: RequestTableMessage.from_json,
    RESIGN_TYPE: ResignMessage.from_json,
    PASS_TOKEN_TYPE: PassTokenMessage.from_json
}


def from_json(jsonstr: str):
    try:
        data = json.loads(jsonstr)
        # if len(data) != 1:
        if not data[TYPE]:
            logger.error("Nieprawidłowy komunikat!")
            return
        # Element type - typ komunikatu
        message_type = data[TYPE]
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


class InternalMessage(Message):
    pass


class InternalReloadMessage(InternalMessage):
    pass


class InternalQuitMessage(InternalMessage):
    def __init__(self, client_id: str):
        self.client_id = client_id
