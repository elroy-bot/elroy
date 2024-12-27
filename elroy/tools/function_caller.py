import inspect
import traceback
from dataclasses import dataclass
from types import FunctionType, ModuleType
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Type,
    Union,
    get_args,
    get_origin,
)

from docstring_parser import parse
from toolz import concat, concatv, merge, pipe
from toolz.curried import do, filter, map, remove

from ..config.ctx import ElroyContext
from ..db.db_models import FunctionCall
from ..utils.utils import first_or_none

PY_TO_JSON_TYPE = {
    int: "integer",
    str: "string",
    bool: "boolean",
    float: "number",
    Optional[str]: "string",
}


def get_json_type(py_type: Type) -> str:
    """
    Returns a string representing the JSON type, and bool indicating if it is required.
    """
    if py_type in PY_TO_JSON_TYPE:
        return PY_TO_JSON_TYPE[py_type]
    if get_origin(py_type) is Union:
        args = get_args(py_type)
        if type(None) in args:  # This is an Optional type
            non_none_args = [arg for arg in args if arg is not type(None)]
            if len(non_none_args) == 1:
                return PY_TO_JSON_TYPE[non_none_args[0]]
    raise ValueError(f"Unsupported type: {py_type}")


def get_modules():
    return []


ERROR_PREFIX = "**Tool call resulted in error: **"


def exec_function_call(ctx: ElroyContext, function_call: FunctionCall) -> str:

    ctx.io.notify_function_call(function_call)

    try:
        function_to_call = get_functions()[function_call.function_name]

        return pipe(
            {"ctx": ctx} if "ctx" in function_to_call.__code__.co_varnames else {},
            lambda d: merge(function_call.arguments, d),
            lambda args: function_to_call.__call__(**args),
            lambda result: str(result) if result is not None else "Success",
            str,
        )  # type: ignore

    except Exception as e:
        verbose_error = f"Failed function call:\n{function_call}\n\n" + "".join(traceback.format_exception(type(e), e, e.__traceback__))

        return pipe(
            f"Failed function call:\n{function_call}\n\n" + "".join(traceback.format_exception(type(e), e, e.__traceback__)),
            do(ctx.io.notify_warning),
            ERROR_PREFIX.__add__,
        )
        ctx.io.notify_warning(verbose_error)
        return f"{ERROR_PREFIX}{verbose_error}"


def get_module_functions(module: ModuleType) -> List[FunctionType]:
    return pipe(
        dir(module),
        map(lambda name: getattr(module, name)),
        filter(lambda _: inspect.isfunction(_) and _.__module__ == module.__name__),
        list,
    )  # type: ignore


@dataclass
class Parameter:
    name: str
    type: Type
    docstring: Optional[str]
    optional: bool
    default: Optional[Any]


def get_function_schema(function: FunctionType) -> Dict:
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

    def validate_first_param_is_elroy_ctx(parameters: Iterator[Parameter]) -> Iterator[Parameter]:
        """
        If the function accepts parameters, the first parameter must be ElroyContext.

        This is because we need to filter out ElroyContext from parameters surfaced to the assistant.
        """
        parameters = iter(parameters)
        first_param = first_or_none(parameters)

        if not first_param:
            # if a function takes no params, we don't need it to be ElroyContext
            yield from []
        else:

            assert isinstance(
                first_param, Parameter
            ), f"expected Parameter for first arg to function {function.__name__} but instead is {type(first_param)}"
            assert (
                first_param.type == ElroyContext
            ), f"First parameter for function {function.__name__} must be ElroyContext, but is instead {first_param.type}"
            assert (
                first_param.name == "ctx"
            ), f"First parameter for function {function.__name__} must be named 'ctx', but is instead {first_param.name}"
            yield from concatv([first_param], parameters)

    assert function.__doc__ is not None, f"Function {function.__name__} has no docstring"
    docstring_dict = {p.arg_name: p.description for p in parse(function.__doc__).params}

    signature = inspect.signature(function)

    return pipe(
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
        validate_first_param_is_elroy_ctx,
        remove(lambda _: _.type == ElroyContext),
        map(validate_parameter),
        map(
            lambda _: [
                _.name,
                {"type": get_json_type(_.type) if _.type != inspect.Parameter.empty else "string", "description": _.docstring},
            ]
        ),
        dict,
        lambda properties: {
            "name": function.__name__,
            "parameters": {"type": "object", "properties": properties},
            "required": [
                name
                for name, param in signature.parameters.items()
                if param.default == inspect.Parameter.empty
                and get_origin(param.annotation) is not Union
                and name not in ["user_id", "session"]
            ],
        },
    )  # type: ignore


def get_function_schemas() -> List[Dict[str, Any]]:
    return pipe(
        get_functions().values(),
        map(get_function_schema),
        map(lambda _: {"type": "function", "function": _}),
        list,
    )  # type: ignore


def get_functions() -> Dict[str, FunctionType]:
    from ..system_commands import ASSISTANT_VISIBLE_COMMANDS

    return pipe(
        get_modules(),
        map(get_module_functions),
        concat,
        list,
        lambda _: concatv(
            _,
            ASSISTANT_VISIBLE_COMMANDS,
        ),
        map(lambda _: [_.__name__, _]),
        dict,
    )


def validate_openai_tool_schema():
    """
    Validates the schema for OpenAI function tools' parameters.

    :param function_schemas: List of function schema dictionaries.
    :returns: Tuple (is_valid, errors). is_valid is a boolean indicating if all schemas are valid.
                Errors is a list of error messages if any issues are detected.
    """
    errors = []

    function_schemas = get_function_schemas()

    if not isinstance(function_schemas, list):
        errors.append("Function schemas should be a list.")
        return False, errors

    for idx, func_schema in enumerate(function_schemas):
        if not isinstance(func_schema, dict):
            errors.append(f"Schema at index {idx} is not a dictionary.")
            continue

        if "type" not in func_schema or func_schema["type"] != "function":
            errors.append(f"Schema at index {idx} is missing 'type' or 'type' is not 'function'.")
        if "function" not in func_schema:
            errors.append(f"Schema at index {idx} is missing 'function' key.")
            continue

        function = func_schema["function"]
        if not isinstance(function, dict):
            errors.append(f"Function schema at index {idx} is not a dictionary.")
            continue

        if "name" not in function:
            errors.append(f"Function schema at index {idx} is missing 'name' key.")

        if "parameters" not in function:
            errors.append(f"Function schema at index {idx} is missing 'parameters' key.")
            continue

        parameters = function["parameters"]
        if not isinstance(parameters, dict) or parameters.get("type") != "object":
            errors.append(f"Parameters for function '{function.get('name')}' must be an object.")

        if "properties" not in parameters or not isinstance(parameters["properties"], dict):
            errors.append(f"'properties' for function '{function.get('name')}' must be a valid dictionary.")

        required_fields = parameters.get("required")
        if required_fields is not None and not isinstance(required_fields, list):
            errors.append(f"'required' for function '{function.get('name')}' must be a list if present.")

    if len(errors) > 0:
        raise ValueError(errors)


validate_openai_tool_schema()
