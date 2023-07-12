import random
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .artifact import Artifact
from .instructions import Instruction
from .operator import InstanceOperatorWithGlobalAccess, StreamInstanceOperator
from .text_utils import split_words


class Renderer(ABC):
    @abstractmethod
    def get_postprocessors(self) -> List[str]:
        pass


class Template(Artifact):
    @abstractmethod
    def process_inputs(self, inputs: Dict[str, object]) -> Dict[str, object]:
        pass

    @abstractmethod
    def process_outputs(self, outputs: Dict[str, object]) -> Dict[str, object]:
        pass

    @abstractmethod
    def get_postprocessors(self) -> List[str]:
        pass


class RenderFormatTemplate(Renderer, StreamInstanceOperator):
    template: Template = None
    random_reference: bool = False

    def verify(self):
        assert isinstance(self.template, Template), "Template must be an instance of Template"
        assert self.template is not None, "Template must be specified"

    def process(self, instance: Dict[str, Any], stream_name: str = None) -> Dict[str, Any]:
        return self.render(instance)

    def render(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        inputs = instance.pop("inputs")
        outputs = instance.pop("outputs")

        source = self.template.process_inputs(inputs)

        key, targets = next(iter(outputs.items()))
        if not isinstance(targets, list):
            targets = [targets]

        references = [self.template.process_outputs({key: target}) for target in targets]

        if self.random_reference:
            target = random.choice(references)
        else:
            if len(references) == 0:
                raise ValueError("No references found")
            target = references[0]  # what

        return {
            **instance,
            "source": source,
            "target": target,
            "references": references,
        }

    def get_postprocessors(self) -> List[str]:
        return self.template.get_postprocessors()


class RenderAutoFormatTemplate(RenderFormatTemplate):
    def prepare(self):
        if self.template is None:
            self.template = AutoInputOutputTemplate()
        elif isinstance(self.template, InputOutputTemplate):
            self.template = AutoInputOutputTemplate(
                input_format=self.template.input_format,
                output_format=self.template.output_format,
            )
        else:
            raise ValueError(
                f"Template must be an instance of InputOutputTemplate or AutoInputOutputTemplate, got {type(self.template)}"
            )

    def render(self, instance: Dict[str, object]) -> Dict[str, object]:
        if not self.template.is_complete():
            self.template.infer_missing(instance["inputs"], instance["outputs"])

        inputs = {key: value for key, value in instance["inputs"].items()}

        return super().render({**instance, "inputs": inputs})


class CharacterSizeLimiter(Artifact):
    limit: int = 1000

    def check(self, text: str) -> bool:
        return len(text) <= self.limit


class RenderTemplatedICL(RenderAutoFormatTemplate):
    instruction: Instruction = None
    input_prefix: str = "Input: "
    output_prefix: str = "Output: "
    instruction_prefix: str = ""
    demos_field: str = None
    size_limiter: Artifact = None
    input_output_separator: str = "\n"
    demo_separator: str = "\n\n"
    demos_cache = None

    def verify(self):
        assert self.demos_cache is None

    def render(self, instance: Dict[str, object]) -> Dict[str, object]:
        if self.demos_cache is None:
            self.demos_cache = instance.pop(self.demos_field, [])
        else:
            instance.pop(self.demos_field, None)

        source = ""

        example = super().render(instance)

        input_str = self.input_prefix + example["source"] + self.input_output_separator + self.output_prefix

        if self.instruction is not None:
            source += self.instruction_prefix + self.instruction() + self.demo_separator

        for demo_instance in self.demos_cache:
            demo_example = super().render(demo_instance)
            demo_str = (
                self.input_prefix
                + demo_example["source"]
                + self.input_output_separator
                + self.output_prefix
                + demo_example["target"]
                + self.demo_separator
            )

            if self.size_limiter is not None:
                if not self.size_limiter.check(source + demo_str + input_str + example["target"]):
                    continue

            source += demo_str

        source += input_str

        return {
            **example,
            "source": source,
        }


class InputOutputTemplate(Template):
    input_format: str = None
    output_format: str = None

    def process_inputs(self, inputs: Dict[str, object]) -> Dict[str, object]:
        return self.input_format.format(**inputs)

    def process_outputs(self, outputs: Dict[str, object]) -> Dict[str, object]:
        return self.output_format.format(**outputs)

    def get_postprocessors(self) -> List[str]:
        return ["to_string"]


class AutoInputOutputTemplate(InputOutputTemplate):
    def infer_input_format(self, inputs):
        input_format = ""
        for key in inputs.keys():
            name = " ".join(word.lower().capitalize() for word in split_words(key) if word != " ")
            input_format += name + ": " + "{" + key + "}" + "\n"
        self.input_format = input_format

    def infer_output_format(self, outputs):
        self.output_format = "{" + next(iter(outputs.keys())) + "}"

    def infer_missing(self, inputs, outputs):
        if self.input_format is None:
            self.infer_input_format(inputs)
        if self.output_format is None:
            self.infer_output_format(outputs)

    def is_complete(self):
        return self.input_format is not None and self.output_format is not None


from .collections import ListCollection


class TemplatesList(ListCollection):
    def verify(self):
        for template in self.items:
            assert isinstance(template, Template)


class TemplatesDict(Dict):
    def verify(self):
        for key, template in self.items():
            assert isinstance(template, Template)