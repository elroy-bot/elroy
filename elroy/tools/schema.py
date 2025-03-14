import inspect
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    Union,
    get_args,
    get_origin,
)

from docstring_parser import parse
from pydantic import BaseModel
from toolz import dissoc, pipe
from toolz.curried import map, remove

PY_TO_JSON_TYPE = {
    int: "integer",
    str: "string",
    bool: "boolean",
    float: "number",
    Optional[str]: "string",
}


def _pydantic_to_openai_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively clean a schema dictionary to match OpenAI's expected format."""
    if not isinstance(schema, dict):
        return schema

    clean = {}
    # Always include type if present
    if "type" in schema:
        clean["type"] = schema["type"]

    # Include description if present
    if "description" in schema:
        clean["description"] = schema["description"]

    # Recursively clean nested properties
    if "properties" in schema:
        clean["properties"] = {k: _pydantic_to_openai_schema(v) for k, v in schema["properties"].items()}

    # Include required fields if present
    if "required" in schema:
        clean["required"] = schema["required"]

    # Recursively clean array items
    if "items" in schema:
        clean["items"] = _pydantic_to_openai_schema(schema["items"])

    return clean


def get_json_type(py_type: Type) -> Union[str, Dict[str, Any]]:
    """
    Returns either:
    - A string representing the JSON type for primitive types
    - A dict containing the full schema for Pydantic models
    """
    if py_type in PY_TO_JSON_TYPE:
        return PY_TO_JSON_TYPE[py_type]

    if get_origin(py_type) is Union:
        args = get_args(py_type)
        if type(None) in args:  # This is an Optional type
            non_none_args = [arg for arg in args if arg is not type(None)]
            if len(non_none_args) == 1:
                return get_json_type(non_none_args[0])

    if isinstance(py_type, type) and issubclass(py_type, BaseModel):
        schema = py_type.model_json_schema()
        return _pydantic_to_openai_schema(schema).get("properties", {})

    raise ValueError(f"Unsupported type: {py_type}")


@dataclass
class Parameter:
    name: str
    type: Type
    docstring: Optional[str]
    optional: bool
    default: Optional[Any]


def get_function_schema(function: Callable) -> Dict:
    """Returns OpenAI function schema for a given function."""

    def validate_parameter(parameter: Parameter) -> Parameter:
        if not parameter.optional:
            assert (
                parameter.type != inspect.Parameter.empty
            ), f"Required parameter {parameter.name} for function {function.__name__} has no type annotation"
        else:
            assert (
                parameter.default != inspect.Parameter.empty
            ), f"Optional parameter {parameter.name} for function {function.__name__} has no default value"
        assert parameter.name in docstring_dict, f"Parameter {parameter.name} for function {function.__name__} has no docstring"
        if parameter.type != inspect.Parameter.empty:
            assert (
                get_json_type(parameter.type) is not None
            ), f"Parameter {parameter.name} for function {function.__name__} has no corresponding JSON schema type"

        return parameter

    assert function.__doc__ is not None, f"Function {function.__name__} has no docstring"
    parsed_docstring = parse(function.__doc__)
    assert parsed_docstring.description, f"Function {function.__name__} has no description in docstring"
    description = parsed_docstring.description.strip()
    docstring_dict = {p.arg_name: p.description for p in parse(function.__doc__).params}

    signature = inspect.signature(function)

    from ..core.ctx import ElroyContext

    properties = pipe(
        signature.parameters.items(),
        map(
            lambda _: Parameter(
                name=_[0],
                type=_[1].annotation,
                docstring=docstring_dict.get(_[0]),
                optional=_[1].default != inspect.Parameter.empty
                or (get_origin(_[1].annotation) is Union and type(None) in get_args(_[1].annotation)),
                default=_[1].default,
            )
        ),
        remove(lambda _: _.type == ElroyContext),
        map(validate_parameter),
        list,
    )

    return pipe(
        properties,
        map(
            lambda _: [
                _.name,
                {
                    **(
                        {"type": "string"}
                        if _.type == inspect.Parameter.empty
                        else (
                            {"type": "object", "properties": get_json_type(_.type)}
                            if isinstance(_.type, type) and issubclass(_.type, BaseModel)
                            else {"type": get_json_type(_.type)}
                        )
                    ),
                    "description": _.docstring,
                },
            ]
        ),
        dict,
        lambda d: {
            "name": function.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": d,
                "required": [p.name for p in properties if not p.optional],  # type: ignore
            },
        },
        lambda d: dissoc(d, "parameters") if not d["parameters"]["properties"] else d,
        lambda d: {"type": "function", "function": d},
    )


def validate_schema(func_schema: Dict[str, Any], has_args: bool) -> List[str]:
    """
    Validates the schema for OpenAI function tools' parameters.

    :param function_schemas: List of function schema dictionaries.
    :returns: Tuple (is_valid, errors). is_valid is a boolean indicating if all schemas are valid.
                Errors is a list of error messages if any issues are detected.
    """
    errors = []

    if "type" not in func_schema or func_schema["type"] != "function":
        errors.append(f"Missing 'type' or 'type' is not 'function'.")
    if "function" not in func_schema:
        errors.append(f"Mssing 'function' key.")
        return errors

    function = func_schema["function"]
    if not isinstance(function, dict):
        errors.append(f"Schema is not a dictionary.")
        return errors

    if "description" not in function:
        errors.append(f"Missing 'description' key.")

    if "name" not in function:
        errors.append(f"Missing 'name' key.")

    if "parameters" not in function:
        if has_args:
            errors.append(f"Function is missing 'parameters' key, required if source function has arguments")
            return errors
        else:
            return errors

    parameters = function["parameters"]
    if not isinstance(parameters, dict) or parameters.get("type") != "object":
        errors.append(f"Parameters for function '{function.get('name')}' must be an object.")

    if "properties" not in parameters or not isinstance(parameters["properties"], dict):
        errors.append(f"'properties' for function '{function.get('name')}' must be a valid dictionary.")

    required_fields = parameters.get("required")
    if required_fields is not None and not isinstance(required_fields, list):
        errors.append(f"'required' for function '{function.get('name')}' must be a list if present.")
    return errors
