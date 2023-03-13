import bpy
from ..node import DreamTexturesNode
from ...generator_process import Generator
from ...generator_process.actions.prompt_to_image import StepPreviewMode
from ...property_groups.dream_prompt import DreamPrompt, control_net_options
from .input_nodes import NodeSceneInfo
import numpy as np
from dataclasses import dataclass
from typing import Any
import enum

class NodeSocketControlNet(bpy.types.NodeSocket):
    bl_idname = "NodeSocketControlNet"
    bl_label = "ControlNet Socket"

    def __init__(self):
        self.link_limit = 0

    def draw(self, context, layout, node, text):
        layout.label(text=text)

    def draw_color(self, context, node):
        return (0.63, 0.63, 0.63, 1)

class ControlType(enum.IntEnum):
    DEPTH = 1
    OPENPOSE = 2
    NORMAL = 3

@dataclass
class ControlNet:
    model: str
    image: Any
    collection: Any
    control_type: ControlType
    conditioning_scale: float

    def control(self, context):
        if self.image is not None:
            return np.flipud(self.image)
        else:
            match self.control_type:
                case ControlType.DEPTH:
                    return np.flipud(NodeSceneInfo.render_depth_map(context, collection=self.collection))
                case ControlType.OPENPOSE:
                    pass
                case ControlType.NORMAL:
                    pass

def _update_stable_diffusion_sockets(self, context):
    self.inputs['Source Image'].enabled = self.task in {'image_to_image', 'depth_to_image'}
    self.inputs['Noise Strength'].enabled = self.task in {'image_to_image', 'depth_to_image'}
    if self.task == 'depth_to_image':
        self.inputs['Noise Strength'].default_value = 1.0
    self.inputs['Depth Map'].enabled = self.task == 'depth_to_image'
    self.inputs['ControlNets'].enabled = self.task != 'depth_to_image'
class NodeStableDiffusion(DreamTexturesNode):
    bl_idname = "dream_textures.node_stable_diffusion"
    bl_label = "Stable Diffusion"

    prompt: bpy.props.PointerProperty(type=DreamPrompt)
    task: bpy.props.EnumProperty(name="", items=(
        ('prompt_to_image', 'Prompt to Image', '', 1),
        ('image_to_image', 'Image to Image', '', 2),
        ('depth_to_image', 'Depth to Image', '', 3),
    ), update=_update_stable_diffusion_sockets)

    def init(self, context):
        self.inputs.new("NodeSocketImage", "Depth Map")
        self.inputs.new("NodeSocketImage", "Source Image")
        self.inputs.new("NodeSocketFloat", "Noise Strength").default_value = 0.75

        self.inputs.new("NodeSocketString", "Prompt")
        self.inputs.new("NodeSocketString", "Negative Prompt")

        self.inputs.new("NodeSocketInt", "Width").default_value = 512
        self.inputs.new("NodeSocketInt", "Height").default_value = 512
        
        self.inputs.new("NodeSocketInt", "Steps").default_value = 25
        self.inputs.new("NodeSocketInt", "Seed")
        self.inputs.new("NodeSocketFloat", "CFG Scale").default_value = 7.50
        
        self.inputs.new("NodeSocketControlNet", "ControlNets")

        self.outputs.new("NodeSocketColor", "Image")

        _update_stable_diffusion_sockets(self, context)

    def draw_buttons(self, context, layout):
        layout.prop(self, "task")
        prompt = self.prompt
        layout.prop(prompt, "pipeline", text="")
        layout.prop(prompt, "model", text="")
        layout.prop(prompt, "scheduler", text="")
    
    def execute(self, context, prompt, negative_prompt, width, height, steps, seed, cfg_scale, controlnets, depth_map, source_image, noise_strength):
        self.prompt.use_negative_prompt = True
        self.prompt.negative_prompt = negative_prompt
        self.prompt.steps = steps
        self.prompt.seed = str(seed)
        self.prompt.cfg_scale = cfg_scale
        args = self.prompt.generate_args()

        shared_args = context.scene.dream_textures_engine_prompt.generate_args()
        
        if controlnets is not None:
            if not isinstance(controlnets, ControlNet):
                controlnets = controlnets[0]
            result = Generator.shared().control_net(
                pipeline=args['pipeline'],
                model=args['model'],
                scheduler=args['scheduler'],
                optimizations=shared_args['optimizations'],
                seamless_axes=args['seamless_axes'],
                iterations=args['iterations'],

                control_net=controlnets.model,
                control=controlnets.control(context),
                controlnet_conditioning_scale=controlnets.conditioning_scale,

                image=np.uint8(source_image * 255) if self.task == 'image_to_image' else None,
                strength=noise_strength,

                prompt=prompt,
                steps=steps,
                seed=seed,
                width=width,
                height=height,
                cfg_scale=cfg_scale,
                use_negative_prompt=True,
                negative_prompt=negative_prompt,
                step_preview_mode=StepPreviewMode.NONE
            ).result()
        else:
            match self.task:
                case 'prompt_to_image':
                    result = Generator.shared().prompt_to_image(
                        pipeline=args['pipeline'],
                        model=args['model'],
                        scheduler=args['scheduler'],
                        optimizations=shared_args['optimizations'],
                        seamless_axes=args['seamless_axes'],
                        iterations=args['iterations'],
                        prompt=prompt,
                        steps=steps,
                        seed=seed,
                        width=width,
                        height=height,
                        cfg_scale=cfg_scale,
                        use_negative_prompt=True,
                        negative_prompt=negative_prompt,
                        step_preview_mode=StepPreviewMode.NONE
                    ).result()
                case 'image_to_image':
                    result = Generator.shared().image_to_image(
                        pipeline=args['pipeline'],
                        model=args['model'],
                        scheduler=args['scheduler'],
                        optimizations=shared_args['optimizations'],
                        seamless_axes=args['seamless_axes'],
                        iterations=args['iterations'],
                        
                        image=np.uint8(source_image * 255),
                        strength=noise_strength,
                        fit=True,

                        prompt=prompt,
                        steps=steps,
                        seed=seed,
                        width=width,
                        height=height,
                        cfg_scale=cfg_scale,
                        use_negative_prompt=True,
                        negative_prompt=negative_prompt,
                        step_preview_mode=StepPreviewMode.NONE
                    ).result()
                case 'depth_to_image':
                    result = Generator.shared().depth_to_image(
                        pipeline=args['pipeline'],
                        model=args['model'],
                        scheduler=args['scheduler'],
                        optimizations=shared_args['optimizations'],
                        seamless_axes=args['seamless_axes'],
                        iterations=args['iterations'],
                        
                        depth=depth_map,
                        image=np.uint8(source_image * 255) if source_image is not None else None,
                        strength=noise_strength,

                        prompt=prompt,
                        steps=steps,
                        seed=seed,
                        width=width,
                        height=height,
                        cfg_scale=cfg_scale,
                        use_negative_prompt=True,
                        negative_prompt=negative_prompt,
                        step_preview_mode=StepPreviewMode.NONE
                    ).result()
        return {
            'Image': result[-1].images[-1]
        }

def _update_control_net_sockets(self, context):
    self.inputs['Collection'].enabled = self.input_type == 'collection'
    self.inputs['Image'].enabled = self.input_type == 'image'
class NodeControlNet(DreamTexturesNode):
    bl_idname = "dream_textures.node_control_net"
    bl_label = "ControlNet"

    control_net: bpy.props.EnumProperty(name="", items=control_net_options)
    input_type: bpy.props.EnumProperty(name="", items=(
        ('collection', 'Collection', '', 1),
        ('image', 'Image', '', 2),
    ), update=_update_control_net_sockets)
    control_type: bpy.props.EnumProperty(name="", items=(
        ('DEPTH', 'Depth', '', 1),
        ('OPENPOSE', 'OpenPose', '', 2),
        ('NORMAL', 'Normal Map', '', 3),
    ))

    def init(self, context):
        self.inputs.new("NodeSocketCollection", "Collection")
        self.inputs.new("NodeSocketColor", "Image")
        self.inputs.new("NodeSocketFloat", "Conditioning Scale").default_value = 1

        self.outputs.new(NodeSocketControlNet.bl_idname, "Control")

        _update_control_net_sockets(self, context)

    def draw_buttons(self, context, layout):
        layout.prop(self, "control_net")
        layout.prop(self, "input_type")
        layout.prop(self, "control_type")
    
    def execute(self, context, collection, image, conditioning_scale):
        return {
            'Control': ControlNet(
                self.control_net,
                image if self.input_type == 'image' else None,
                collection if self.input_type == 'collection' else None,
                ControlType[self.control_type],
                conditioning_scale
            )
        }