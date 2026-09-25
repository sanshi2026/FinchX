"""Static checks for release workflow dependencies and artifact naming."""

import re
from pathlib import Path


WORKFLOW_PATH = Path(__file__).parents[1] / ".github" / "workflows" / "release.yml"


def _job_block(workflow: str, job_name: str) -> str:
    jobs = list(re.finditer(r"(?m)^  (validate|test|build|publish):\s*$", workflow))
    for index, match in enumerate(jobs):
        if match.group(1) == job_name:
            end = jobs[index + 1].start() if index + 1 < len(jobs) else len(workflow)
            return workflow[match.start() : end]
    raise AssertionError(f"missing {job_name!r} job in release workflow")


def _needs(job: str) -> set[str]:
    match = re.search(r"(?m)^    needs:\s*(.+?)\s*$", job)
    assert match, "job must declare direct dependencies"
    value = match.group(1)
    if value.startswith("[") and value.endswith("]"):
        return {item.strip() for item in value[1:-1].split(",") if item.strip()}
    return {value}


def _step_block(job: str, step_name: str) -> str:
    match = re.search(
        rf"(?ms)^      - name: {re.escape(step_name)}\n(.*?)(?=^      - name:|\Z)",
        job,
    )
    assert match, f"missing {step_name!r} step"
    return match.group(1)


def _artifact_name(job: str, step_name: str) -> str:
    step = _step_block(job, step_name)
    match = re.search(r"(?m)^\s+name:\s*(.+?)\s*$", step)
    assert match, f"{step_name!r} step must name its artifact"
    return match.group(1)


def test_release_version_outputs_are_available_to_artifact_jobs():
    workflow = WORKFLOW_PATH.read_text()
    validate = _job_block(workflow, "validate")
    test = _job_block(workflow, "test")
    build = _job_block(workflow, "build")
    publish = _job_block(workflow, "publish")

    assert re.search(
        r"(?m)^      version: \$\{\{ steps\.release\.outputs\.version \}\}$",
        validate,
    )
    assert _needs(test) == {"validate"}
    assert _needs(build) == {"validate", "test"}
    assert _needs(publish) == {"validate", "build"}

    upload_name = _artifact_name(build, "Upload release artifacts")
    download_name = _artifact_name(publish, "Download validated release artifacts")
    assert upload_name == download_name
    assert "${{ needs.validate.outputs.version }}" in upload_name
    assert "${{ needs.validate.outputs.version }}" in publish
