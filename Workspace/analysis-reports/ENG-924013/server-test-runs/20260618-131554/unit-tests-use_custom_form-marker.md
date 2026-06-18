# New unit tests for use_custom_form runtime-file gating

## Command
```bash
cd ~/Workspace/calm-dsl && source venv/bin/activate
python -m pytest tests/unit/test_custom_form.py::TestCustomFormRuntimeLaunchGating -v
```

## Output
```
tests/unit/test_custom_form.py::TestCustomFormRuntimeLaunchGating::test_marker_is_internal_not_written_into_file PASSED [ 20%]
tests/unit/test_custom_form.py::TestCustomFormRuntimeLaunchGating::test_detects_custom_form_runtime_file_by_suffix PASSED [ 40%]
tests/unit/test_custom_form.py::TestCustomFormRuntimeLaunchGating::test_plain_launch_file_is_not_custom_form_runtime PASSED [ 60%]
tests/unit/test_custom_form.py::TestCustomFormRuntimeLaunchGating::test_suffix_constant_matches_generated_filename PASSED [ 80%]
tests/unit/test_custom_form.py::TestCustomFormRuntimeLaunchGating::test_error_message_mentions_filename_and_requirement PASSED [100%]
============================== 5 passed in 2.86s ===============================
```

## Full custom_form suite
```
60 passed, 58 warnings in 2.90s
```
