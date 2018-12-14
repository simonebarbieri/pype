# :coding: utf-8
# :copyright: Copyright (c) 2017 ftrack
import sys
import argparse
import logging
import os
import json
import ftrack_api
from ftrack_action_handler import BaseAction

from avalon import io, inventory, lib
from avalon.vendor import toml


class AvalonIdAttribute(BaseAction):
    '''Edit meta data action.'''

    #: Action identifier.
    identifier = 'avalon.id.attribute'
    #: Action label.
    label = 'Create Avalon Attribute'
    #: Action description.
    description = 'Creates Avalon/Mongo ID for double check'


    def discover(self, session, entities, event):
        '''
        Validation
        - action is only for Administrators
        '''
        success = False
        userId = event['source']['user']['id']
        user = session.query('User where id is ' + userId).one()
        for role in user['user_security_roles']:
            if role['security_role']['name'] == 'Administrator':
                success = True

        return success


    def launch(self, session, entities, event):
        # JOB SETTINGS

        userId = event['source']['user']['id']
        user = session.query('User where id is ' + userId).one()

        job = session.create('Job', {
            'user': user,
            'status': 'running',
            'data': json.dumps({
                'description': 'Custom Attribute creation.'
            })
        })
        session.commit()
        try:
            # Checkbox for event sync
            cbxSyncName = 'avalon_auto_sync'
            cbxSyncLabel = 'Avalon auto-sync'
            cbxSyncExist = False

            # Attribute Name and Label
            custAttrName = 'avalon_mongo_id'
            custAttrLabel = 'Avalon/Mongo Id'

            attrs_update = set()
            # Types that don't need object_type_id
            base = {'show'}

            # Don't create custom attribute on these entity types:
            exceptions = ['task', 'milestone']
            exceptions.extend(base)
            # Get all possible object types
            all_obj_types = session.query('ObjectType').all()
            count_types = len(all_obj_types)
            # Filter object types by exceptions
            for index in range(count_types):
                i = count_types - 1 - index
                name = all_obj_types[i]['name'].lower()

                if " " in name:
                    name = name.replace(" ","")

                if name in exceptions:
                    all_obj_types.pop(i)

            # Get IDs of filtered object types
            all_obj_types_id = set()

            for obj in all_obj_types:
                all_obj_types_id.add(obj['id'])

            # Get all custom attributes
            current_cust_attr = session.query('CustomAttributeConfiguration').all()
            # Filter already existing AvalonMongoID attr.
            for attr in current_cust_attr:
                if attr['key'] == cbxSyncName:
                    cbxSyncExist = True
                    cbxAttribute = attr
                if attr['key'] == custAttrName:
                    if attr['entity_type'] in base:
                        base.remove(attr['entity_type'])
                        attrs_update.add(attr)
                    if attr['object_type_id'] in all_obj_types_id:
                        all_obj_types_id.remove(attr['object_type_id'])
                        attrs_update.add(attr)

            # Set session back to begin("session.query" raises error on commit)
            session.rollback()
            # Set security roles for attribute
            role_api = session.query('SecurityRole where name is "API"').one()
            role_admin = session.query('SecurityRole where name is "Administrator"').one()
            roles = [role_api,role_admin]

            # Set Text type of Attribute
            custom_attribute_type = session.query(
                'CustomAttributeType where name is "text"'
            ).one()
            # Get/Set 'avalon' group
            groups = session.query('CustomAttributeGroup where name is "avalon"').all()
            if len(groups) > 1:
                msg = "There are more Custom attribute groups with name 'avalon'"
                self.log.warning(msg)
                return { 'success': False, 'message':msg }

            elif len(groups) < 1:
                group = session.create('CustomAttributeGroup', {
                    'name': 'avalon',
                })
                session.commit()
            else:
                group = groups[0]

            # Checkbox for auto-sync event / Create or Update(roles + group)
            if cbxSyncExist is False:
                cbxType = session.query('CustomAttributeType where name is "boolean"').first()
                session.create('CustomAttributeConfiguration', {
                    'entity_type': 'show',
                    'type': cbxType,
                    'label': cbxSyncLabel,
                    'key': cbxSyncName,
                    'default': False,
                    'write_security_roles': roles,
                    'read_security_roles': roles,
                    'group':group,
                })
            else:
                cbxAttribute['write_security_roles'] = roles
                cbxAttribute['read_security_roles'] = roles
                cbxAttribute['group'] = group

            for entity_type in base:
                # Create a custom attribute configuration.
                session.create('CustomAttributeConfiguration', {
                    'entity_type': entity_type,
                    'type': custom_attribute_type,
                    'label': custAttrLabel,
                    'key': custAttrName,
                    'default': '',
                    'write_security_roles': roles,
                    'read_security_roles': roles,
                    'group':group,
                    'config': json.dumps({'markdown': False})
                })

            for type in all_obj_types_id:
                # Create a custom attribute configuration.
                session.create('CustomAttributeConfiguration', {
                    'entity_type': 'task',
                    'object_type_id': type,
                    'type': custom_attribute_type,
                    'label': custAttrLabel,
                    'key': custAttrName,
                    'default': '',
                    'write_security_roles': roles,
                    'read_security_roles': roles,
                    'group':group,
                    'config': json.dumps({'markdown': False})
                })

            for attr in attrs_update:
                attr['write_security_roles'] = roles
                attr['read_security_roles'] = roles
                attr['group'] = group

            job['status'] = 'done'
            session.commit()

        except Exception as e:
            session.rollback()
            job['status'] = 'failed'
            session.commit()
            self.log.error("Creating custom attributes failed ({})".format(e))

        return True


def register(session, **kw):
    '''Register plugin. Called when used as an plugin.'''

    # Validate that session is an instance of ftrack_api.Session. If not,
    # assume that register is being called from an old or incompatible API and
    # return without doing anything.
    if not isinstance(session, ftrack_api.session.Session):
        return

    action_handler = AvalonIdAttribute(session)
    action_handler.register()


def main(arguments=None):
    '''Set up logging and register action.'''
    if arguments is None:
        arguments = []

    parser = argparse.ArgumentParser()
    # Allow setting of logging level from arguments.
    loggingLevels = {}
    for level in (
        logging.NOTSET, logging.DEBUG, logging.INFO, logging.WARNING,
        logging.ERROR, logging.CRITICAL
    ):
        loggingLevels[logging.getLevelName(level).lower()] = level

    parser.add_argument(
        '-v', '--verbosity',
        help='Set the logging output verbosity.',
        choices=loggingLevels.keys(),
        default='info'
    )
    namespace = parser.parse_args(arguments)

    # Set up basic logging
    logging.basicConfig(level=loggingLevels[namespace.verbosity])

    session = ftrack_api.Session()
    register(session)

    # Wait for events
    logging.info(
        'Registered actions and listening for events. Use Ctrl-C to abort.'
    )
    session.event_hub.wait()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))