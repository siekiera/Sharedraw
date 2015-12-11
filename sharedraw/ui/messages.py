import json
import logging

logger = logging.getLogger(__name__)


class Message:
    """
    Komunikat do wymiany danych z innymi użytkownikami
    """
    def to_json(self):
        pass


class ImageMessage(Message):
    """
    Komunikat służący do przesłania danych o obrazie
    """
    def __init__(self, changed_pxs: []):
        self.changed_pxs = changed_pxs

    @staticmethod
    def from_json(msg: {}):
        if not msg['coords']:
            logger.error('No coords!')
        changed_pxs = list(map(lambda coord_obj: (coord_obj['x'], coord_obj['y']), msg['coords']))
        return ImageMessage(changed_pxs)

    def to_json(self):
        data = list(map(lambda xy: {'x': xy[0], 'y': xy[1]}, self.changed_pxs))
        msg = {'image': {
            'clientId': 'foo',
            'coords': data,
            'startLine': 'true',
            'color': '0'
        }}
        return json.dumps(msg)

message_type_handlers = {
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