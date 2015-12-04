import json
import logging

logger = logging.getLogger(__name__)


class Message:
    def from_json(self, jsonstr: str):
        pass

    def to_json(self):
        pass


class ImageMessage(Message):
    def __init__(self, changed_pxs: []):
        self.changed_pxs = changed_pxs

    def from_json(self, jsonstr: str):
        msg = json.loads(jsonstr)
        if not msg['coords']:
            logger.error('No coords!')
        changed_pxs = list(filter(lambda coord_obj: (coord_obj['x'], coord_obj['y']), msg['coords']))
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