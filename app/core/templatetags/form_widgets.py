from django import forms, template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def bootstrap_field(bound_field):
    widget = bound_field.field.widget
    input_type = getattr(widget, "input_type", "")

    if input_type == "checkbox":
        bootstrap_class = "form-check-input"
    elif isinstance(widget, forms.Select):
        bootstrap_class = "form-select"
    else:
        bootstrap_class = "form-control"

    classes = _merge_classes(widget.attrs.get("class", ""), bootstrap_class)
    if bound_field.errors:
        classes = _merge_classes(classes, "is-invalid")

    attrs = {"class": classes}
    if bound_field.errors:
        attrs["aria-invalid"] = "true"

    return mark_safe(bound_field.as_widget(attrs=attrs))


def _merge_classes(*class_values):
    classes = []
    for class_value in class_values:
        for class_name in str(class_value).split():
            if class_name not in classes:
                classes.append(class_name)
    return " ".join(classes)
