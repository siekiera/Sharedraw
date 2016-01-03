import json
import logging

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
        if not msg['coords']:
            logger.error('No coords!')
        changed_pxs = list(map(lambda coord_obj: (coord_obj['x'], coord_obj['y']), msg['coords']))
        return PaintMessage(changed_pxs, 'white' if msg['color'] == '255' else 'black')

    def to_json(self):
        data = list(map(lambda xy: {'x': xy[0], 'y': xy[1]}, self.changed_pxs))
        msg = {'paint': {
            'clientId': 'foo',
            'coords': data,
            'startLine': 'true',
            'color': '255' if self.color == 'white' else '0'
        }}
        return json.dumps(msg)


class ImageMessage(Message):
    """ Komunikat zawierający aktualny stan tablicy po dołączeniu się klienta
    """

    def __init__(self, client_id):
        self.client_id = client_id

    @staticmethod
    def from_json(msg: {}):
        # TODO: na razie brak obsługi danych obrazu, pobieramy tylko clientId
        if not msg['clientId']:
            logger.error('No clientId!')
        return JoinMessage(msg['clientId'])

    def to_json(self):
        # TODO: na razie brak obsługi danych obrazu, pobieramy tylko clientId
        msg = {'image': {
            'clientId': self.client_id,
            'imagePart': None,
            'partId': 0,
            'partsAmount': 1
        }}
        return json.dumps(msg)


class JoinMessage(Message):
    """ Komunikat potwiedzający dołączenie się klienta
    """

    def __init__(self, client_id: str):
        self.client_id = client_id

    @staticmethod
    def from_json(msg: {}):
        if not msg['clientId']:
            logger.error('No clientId!')
        return JoinMessage(msg['clientId'])

    def to_json(self):
        msg = {'joined': {
            'clientId': self.client_id
        }}
        return json.dumps(msg)


message_type_handlers = {
    'paint': PaintMessage.from_json,
    'joined': JoinMessage.from_json,
    'image': ImageMessage.from_json
}


def from_json(jsonstr: str):
    data = json.loads(jsonstr)
    if len(data) != 1:
        logger.error("Nieprawidłowy komunikat!")
        return
    # Klucz pierwszego elementu - typ komunikatu
    message_type = list(data.keys())[0]
    h = message_type_handlers.get(message_type)
    if not h:
        logger.error("Nieznany typ komunikatu: %s" % message_type)
    # Wywołanie funkcji obsługującej: f(jsonobj)
    return h(data[message_type])