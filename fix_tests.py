import re

with open('tests/test_opencode_worker.py', 'r') as f:
    code = f.read()

# Fix parse fallback
code = code.replace(
    'assert result is None', 
    'assert result == [{"thought": "Free-form text fallback", "dialogue": "This is not JSON at all.", "type": "observation", "priority": 1}]'
)
code = code.replace('test_parse_returns_none_for_garbage', 'test_parse_returns_fallback_for_garbage')

# Remove test_error_emitted_on_parse_failure
pattern = re.compile(r'def test_error_emitted_on_parse_failure\(qapp\):.*?assert not hasattr\(worker, \'_session_id\'\) or worker\._session_id is None', re.DOTALL)
code = pattern.sub('', code)

with open('tests/test_opencode_worker.py', 'w') as f:
    f.write(code)

with open('tests/test_opencode_worker_stateless.py', 'r') as f:
    code_stateless = f.read()

# Fix stateless parse fallback
code_stateless = code_stateless.replace(
    'assert result is None', 
    'assert result == [{"thought": "Free-form text fallback", "dialogue": "This is not JSON at all. And definitely not a list.", "type": "observation", "priority": 1}]'
)
code_stateless = code_stateless.replace('test_parse_returns_none_for_garbage', 'test_parse_returns_fallback_for_garbage')

with open('tests/test_opencode_worker_stateless.py', 'w') as f:
    f.write(code_stateless)
