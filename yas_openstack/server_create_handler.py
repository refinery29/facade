from novaclient.exceptions import Forbidden

from yas_openstack.openstack_handler import OpenStackHandler
from yas_openstack.server import NoServersFound, MultipleServersFound


def _parse_meta(meta_string):
    if meta_string:
        try:
            meta_dict = dict(pair.split('=') for pair in meta_string.split(','))
        except ValueError as e:
            raise ValueError('Invalid meta, format must be "key=value,key=value..."')
    else:
        meta_dict = None
    return meta_dict

class OpenStackServerCreateHandler(OpenStackHandler):

    def __init__(self, *args, **kwargs):
        super().__init__('(?:launch|start|create)\ ([-\w]+)'
                         '(?:\ on\ )?([-\w]+:?[-\w]+)?'
                         '(?:\ meta\ )?([\w=,]+)?'
                         '(?:\ from\ )?([-:/\w]+)?',
                         *args, **kwargs)
        self.log('DEBUG', f'Initializing OpenStack server create handler with defaults:\n{self.config.__dict__}')

    def __get_user_info(self, user_id):
        try:
            creator_info = self.api_call('users.info', user=user_id)
        except Exception as e:
            self.log('WARN', f"Caught {e} while retrieving creator_info.")
            creator_info = None
        return creator_info

    def handle(self, data, reply):
        name, branch, meta_string, image = self.current_match.groups()
        self.log('INFO', f"Received request for {name} on {branch} from {image}")
        reply(f"Received request for creation of {name}", thread=data['ts'])

        if self.server_manager.findall(name=name):
            return reply(f"{name} already exists.")

        userdata = self.template.render(meta=meta_string, name=name, branch=branch or '', data=data)

        meta = _parse_meta(meta_string)

        creator_info = self.__get_user_info(data['user'])
        if creator_info:
            meta['owner'] = creator_info['user']['profile']['real_name']

        meta['init'] = 'pending'
        meta['branch'] = branch

        try:
            server = self.server_manager.create(name, userdata=userdata, image=image, meta=meta)
        except Forbidden as forbidden:
            if "Quota exceeded" in forbidden.message:
                return reply(forbidden.message)
            raise forbidden

        reply(f'Requested creation of {name} with id {server.id}', thread=data['ts'])
        self.log('DEBUG', f'Created used userdata:\n{userdata}')
