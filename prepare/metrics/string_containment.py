from unitxt import add_to_catalog
from unitxt.metrics import StringContainment
from unitxt.test_utils.metrics import test_metric

metric = StringContainment()

predictions = ["barak obama is a politician", "David Gilmour is an English guitarist"]
references = [["politician", "politic", "pol"], ["artist"]]

instance_targets = [
    {"string_containment": 1.0, "score": 1.0, "score_name": "string_containment"},
    {"string_containment": 0.0, "score": 0.0, "score_name": "string_containment"},
]

global_target = {
    "string_containment": 0.50,
    "score": 0.50,
    "score_name": "string_containment",
    "score_ci_high": 1.0,
    "score_ci_low": 0.0,
    "string_containment_ci_high": 1.0,
    "string_containment_ci_low": 0.0,
}

outputs = test_metric(
    metric=metric,
    predictions=predictions,
    references=references,
    instance_targets=instance_targets,
    global_target=global_target,
)

add_to_catalog(metric, "metrics.string_containment", overwrite=True)
