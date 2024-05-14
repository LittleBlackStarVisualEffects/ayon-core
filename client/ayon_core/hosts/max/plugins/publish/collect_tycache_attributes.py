import pyblish.api
import re
import copy
from ayon_core.lib import BoolDef
from ayon_core.pipeline.publish import AYONPyblishPluginMixin
from pymxs import runtime as rt


class CollectTyFlowData(pyblish.api.InstancePlugin,
                        AYONPyblishPluginMixin):
    """Collect Channel Attributes for TyCache Export"""

    order = pyblish.api.CollectorOrder + 0.005
    label = "Collect tyCache attribute Data"
    hosts = ['max']
    families = ["tyflow"]
    validate_tycache_frame_range = True

    @classmethod
    def apply_settings(cls, project_settings):

        settings = (
            project_settings["max"]["publish"]["ValidateTyCacheFrameRange"]
        )
        cls.validate_tycache_frame_range = settings["active"]

    def process(self, instance):
        context = instance.context
        container_name = instance.data["instance_node"]
        container = rt.GetNodeByName(container_name)
        tyc_product_names = [
            name for name
            in container.modifiers[0].AYONTyCacheData.tyc_exports
        ]
        attr_values = self.get_attr_values_from_data(instance.data)
        for tyc_product_name in tyc_product_names:
            self.log.debug(f"Creating instance for operator:{tyc_product_name}")
            tyc_instance = context.create_instance(tyc_product_name)
            tyc_instance[:] = instance[:]
            tyc_instance.data.update(copy.deepcopy(dict(instance.data)))
            # Replace all runs of whitespace with underscore
            prod_name = re.sub(r"\s+", "_", tyc_product_name)
            export_mode = instance.data["tyc_exportMode"]
            tyc_instance.data.update({
                "name": f"{container_name}_{prod_name}",
                "label": f"{container_name}_{prod_name}",
                "family": export_mode,
                "families": [export_mode],
                "productName": f"{container_name}_{prod_name}",
                # get the name of operator for the export
                "operatorName": tyc_product_name,
                "exportMode": (
                    2 if instance.data["tyc_exportMode"] == "tycache" else 6),
                "material_cache": attr_values.get("material"),
                "productType": export_mode,
                "creator_identifier": (
                    f"io.openpype.creators.max.{export_mode}"),
                "publish_attributes": {
                    "ValidateTyCacheFrameRange": {
                        "active": attr_values.get("has_frame_range_validator")}
                }
            })
            instance.append(tyc_instance)

    @classmethod
    def get_attribute_defs(cls):
        return [
            BoolDef("has_frame_range_validator",
                    label="Validate TyCache Frame Range",
                    default=cls.validate_tycache_frame_range),
            BoolDef("material",
                    label="Publish along with Material",
                    default=True)
        ]