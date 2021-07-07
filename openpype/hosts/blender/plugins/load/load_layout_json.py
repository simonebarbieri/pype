"""Load a layout in Blender."""

from pathlib import Path
from pprint import pformat
from typing import Dict, Optional

import bpy
import json

from avalon import api
from avalon.blender.pipeline import AVALON_CONTAINERS
from avalon.blender.pipeline import AVALON_CONTAINER_ID
from avalon.blender.pipeline import AVALON_PROPERTY
from openpype.hosts.blender.api import plugin


class JsonLayoutLoader(plugin.AssetLoader):
    """Load layout published from Unreal."""

    families = ["layout"]
    representations = ["json"]

    label = "Load Layout"
    icon = "code-fork"
    color = "orange"

    animation_creator_name = "CreateAnimation"

    def _remove(self, asset_group):
        objects = list(asset_group.children)

        for obj in objects:
            api.remove(obj.get(AVALON_PROPERTY))

    def _get_loader(self, loaders, family):
        name = ""
        if family == 'rig':
            name = "BlendRigLoader"
        elif family == 'model':
            name = "BlendModelLoader"

        if name == "":
            return None

        for loader in loaders:
            if loader.__name__ == name:
                return loader

        return None

    def _process(self, libpath, asset_group, actions):
        bpy.ops.object.select_all(action='DESELECT')

        with open(libpath, "r") as fp:
            data = json.load(fp)

        all_loaders = api.discover(api.Loader)

        for element in data:
            reference = element.get('reference')
            family = element.get('family')

            loaders = api.loaders_from_representation(all_loaders, reference)
            loader = self._get_loader(loaders, family)

            if not loader:
                continue

            instance_name = element.get('instance_name')

            action = None

            if actions:
                action = actions.get(instance_name, None)

            options = {
                'parent': asset_group,
                'transform': element.get('transform'),
                'action': action
            }

            # This should return the loaded asset, but the load call will be
            # added to the queue to run in the Blender main thread, so
            # at this time it will not return anything. The assets will be
            # loaded in the next Blender cycle, so we use the options to
            # set the transform, parent and assign the action, if there is one.
            api.load(
                loader,
                reference,
                namespace=instance_name,
                options=options
            )

    def process_asset(self,
                      context: dict,
                      name: str,
                      namespace: Optional[str] = None,
                      options: Optional[Dict] = None):
        """
        Arguments:
            name: Use pre-defined name
            namespace: Use pre-defined namespace
            context: Full parenthood of representation to load
            options: Additional settings dictionary
        """
        libpath = self.fname
        asset = context["asset"]["name"]
        subset = context["subset"]["name"]

        asset_name = plugin.asset_name(asset, subset)
        unique_number = plugin.get_unique_number(asset, subset)
        group_name = plugin.asset_name(asset, subset, unique_number)
        namespace = namespace or f"{asset}_{unique_number}"

        avalon_container = bpy.data.collections.get(AVALON_CONTAINERS)
        if not avalon_container:
            avalon_container = bpy.data.collections.new(name=AVALON_CONTAINERS)
            bpy.context.scene.collection.children.link(avalon_container)

        asset_group = bpy.data.objects.new(group_name, object_data=None)
        asset_group.empty_display_type = 'SINGLE_ARROW'
        avalon_container.objects.link(asset_group)

        self._process(libpath, asset_group, None)

        bpy.context.scene.collection.objects.link(asset_group)

        asset_group[AVALON_PROPERTY] = {
            "schema": "openpype:container-2.0",
            "id": AVALON_CONTAINER_ID,
            "name": name,
            "namespace": namespace or '',
            "loader": str(self.__class__.__name__),
            "representation": str(context["representation"]["_id"]),
            "libpath": libpath,
            "asset_name": asset_name,
            "parent": str(context["representation"]["parent"]),
            "family": context["representation"]["context"]["family"],
            "objectName": group_name
        }

        self[:] = asset_group.children
        return asset_group.children

    def exec_update(self, container: Dict, representation: Dict):
        """Update the loaded asset.

        This will remove all objects of the current collection, load the new
        ones and add them to the collection.
        If the objects of the collection are used in another collection they
        will not be removed, only unlinked. Normally this should not be the
        case though.
        """
        object_name = container["objectName"]
        asset_group = bpy.data.objects.get(object_name)
        libpath = Path(api.get_representation_path(representation))
        extension = libpath.suffix.lower()

        self.log.info(
            "Container: %s\nRepresentation: %s",
            pformat(container, indent=2),
            pformat(representation, indent=2),
        )

        assert asset_group, (
            f"The asset is not loaded: {container['objectName']}"
        )
        assert libpath, (
            "No existing library file found for {container['objectName']}"
        )
        assert libpath.is_file(), (
            f"The file doesn't exist: {libpath}"
        )
        assert extension in plugin.VALID_EXTENSIONS, (
            f"Unsupported file: {libpath}"
        )

        metadata = asset_group.get(AVALON_PROPERTY)
        group_libpath = metadata["libpath"]

        normalized_group_libpath = (
            str(Path(bpy.path.abspath(group_libpath)).resolve())
        )
        normalized_libpath = (
            str(Path(bpy.path.abspath(str(libpath))).resolve())
        )
        self.log.debug(
            "normalized_group_libpath:\n  %s\nnormalized_libpath:\n  %s",
            normalized_group_libpath,
            normalized_libpath,
        )
        if normalized_group_libpath == normalized_libpath:
            self.log.info("Library already loaded, not updating...")
            return

        actions = {}

        for obj in asset_group.children:
            obj_meta = obj.get(AVALON_PROPERTY)
            if obj_meta.get('family') == 'rig':
                rig = None
                for child in obj.children:
                    if child.type == 'ARMATURE':
                        rig = child
                        break
                if not rig:
                    raise Exception("No armature in the rig asset group.")
                if rig.animation_data and rig.animation_data.action:
                    instance_name = obj_meta.get('instance_name')
                    actions[instance_name] = rig.animation_data.action

        mat = asset_group.matrix_basis.copy()

        self._remove(asset_group)

        self._process(str(libpath), asset_group, actions)

        asset_group.matrix_basis = mat

        metadata["libpath"] = str(libpath)
        metadata["representation"] = str(representation["_id"])

    def exec_remove(self, container: Dict) -> bool:
        """Remove an existing container from a Blender scene.

        Arguments:
            container (openpype:container-1.0): Container to remove,
                from `host.ls()`.

        Returns:
            bool: Whether the container was deleted.
        """
        object_name = container["objectName"]
        asset_group = bpy.data.objects.get(object_name)

        if not asset_group:
            return False

        self._remove(asset_group)

        bpy.data.objects.remove(asset_group)

        return True