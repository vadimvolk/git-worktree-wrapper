"""Template evaluation engine using simpleeval with strict type checking."""

from __future__ import annotations

import re
from typing import Any, Callable

from simpleeval import EvalWithCompoundTypes, FunctionNotDefined, NameNotDefined

from gww.template.functions import TemplateContext, create_function_registry


class TemplateError(Exception):
    """Base exception for template-related errors."""

    pass


class FunctionTypeError(TemplateError):
    """Raised when function arguments have wrong types."""

    pass


class ContextError(TemplateError):
    """Raised when required context variable is missing."""

    pass


class StrictSimpleEval(EvalWithCompoundTypes):  # type: ignore[misc]
    """Subclass of simpleeval with strict type checking.

    Provides:
    - Type validation for function arguments
    - Clear error messages with context
    - Safe evaluation of predicates and templates
    """

    def __init__(
        self,
        functions: dict[str, Callable[..., Any]] | None = None,
        names: dict[str, Any] | None = None,
    ) -> None:
        """Initialize with custom functions and names.

        Args:
            functions: Dictionary of functions available during evaluation.
            names: Dictionary of variables available during evaluation.
        """
        super().__init__(functions=functions or {}, names=names or {})


# Pattern to match function calls in templates: function_name(args)
FUNCTION_CALL_PATTERN = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^()]*)\)")

# Escape sequences for literal parentheses
ESCAPE_OPEN = "\x00ESCAPE_OPEN\x00"
ESCAPE_CLOSE = "\x00ESCAPE_CLOSE\x00"


def _preprocess_template(template: str) -> tuple[str, list[tuple[str, str]]]:
    """Preprocess template to extract function calls.

    Handles:
    - Escaped parentheses (( -> single (
    - Function call extraction

    Args:
        template: Raw template string.

    Returns:
        Tuple of (preprocessed template with placeholders, list of (placeholder, expression) tuples).
    """
    # Replace escaped parentheses
    processed = template.replace("((", ESCAPE_OPEN)
    processed = processed.replace("))", ESCAPE_CLOSE)

    # Find and extract function calls
    function_calls: list[tuple[str, str]] = []
    placeholder_idx = 0

    def replace_function(match: re.Match[str]) -> str:
        nonlocal placeholder_idx
        func_name = match.group(1)
        args = match.group(2)
        expression = f"{func_name}({args})"
        placeholder = f"\x01FUNC_{placeholder_idx}\x01"
        function_calls.append((placeholder, expression))
        placeholder_idx += 1
        return placeholder

    # Repeatedly find function calls (handles simple nesting)
    prev = None
    while prev != processed:
        prev = processed
        processed = FUNCTION_CALL_PATTERN.sub(replace_function, processed)

    return processed, function_calls


def _postprocess_template(template: str) -> str:
    """Restore escaped parentheses in template.

    Args:
        template: Template with escape sequences.

    Returns:
        Template with single parentheses restored.
    """
    result = template.replace(ESCAPE_OPEN, "(")
    result = result.replace(ESCAPE_CLOSE, ")")
    return result


def evaluate_template(
    template: str,
    context: TemplateContext,
) -> str:
    """Evaluate a path template string.

    Template syntax:
    - Function calls: path(-1), branch(), norm_branch("_")
    - Escaped parentheses: (( -> (
    - Static text: passed through as-is

    Args:
        template: Template string to evaluate.
        context: Template context with URI, branch, etc.

    Returns:
        Evaluated template string.

    Raises:
        TemplateError: If evaluation fails.
        FunctionTypeError: If function arguments are invalid.
        ContextError: If required context is missing.
    """
    # Create function registry
    functions = create_function_registry(context)

    # Preprocess template
    processed, function_calls = _preprocess_template(template)

    # Evaluate each function call
    evaluator = StrictSimpleEval(functions=functions)

    for placeholder, expression in function_calls:
        try:
            result = evaluator.eval(expression)
            if not isinstance(result, str):
                result = str(result)
            processed = processed.replace(placeholder, result)
        except FunctionNotDefined as e:
            raise TemplateError(f"Unknown function in template: {e}") from e
        except NameNotDefined as e:
            raise TemplateError(f"Unknown variable in template: {e}") from e
        except ValueError as e:
            raise ContextError(str(e)) from e
        except TypeError as e:
            raise FunctionTypeError(f"Invalid argument types: {e}") from e
        except Exception as e:
            raise TemplateError(f"Template evaluation failed: {e}") from e

    # Postprocess to restore escaped parentheses
    return _postprocess_template(processed)


def evaluate_predicate(
    predicate: str,
    variables: dict[str, Any],
) -> bool:
    """Evaluate a predicate expression.

    Predicate syntax:
    - Comparison: host == "github.com"
    - Contains: "github" in host
    - Logical: not contains(host, "scp") and len(path) > 1

    Args:
        predicate: Predicate expression string.
        variables: Dictionary of variables and functions for evaluation.
                   Callable values are treated as functions, others as variables.

    Returns:
        Boolean result of predicate evaluation.

    Raises:
        TemplateError: If evaluation fails or result is not boolean.
    """
    # Separate functions from variables
    functions: dict[str, Callable[..., Any]] = {}
    names: dict[str, Any] = {}
    
    for key, value in variables.items():
        if callable(value):
            functions[key] = value
        else:
            names[key] = value
    
    evaluator = StrictSimpleEval(functions=functions, names=names)

    try:
        result = evaluator.eval(predicate)
    except FunctionNotDefined as e:
        raise TemplateError(f"Unknown function in predicate: {e}") from e
    except NameNotDefined as e:
        raise TemplateError(f"Unknown variable in predicate: {e}") from e
    except Exception as e:
        raise TemplateError(f"Predicate evaluation failed: {e}") from e

    if not isinstance(result, bool):
        raise TemplateError(
            f"Predicate must evaluate to boolean, got {type(result).__name__}: {predicate}"
        )

    return result
