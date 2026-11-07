class InputSanitizer:

    # ── Filename Sanitization ──
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        import re, os
        # Remove any directory components (path traversal prevention)
        filename = os.path.basename(filename)
        # Remove null bytes
        filename = filename.replace('\x00', '')
        # Allow only safe characters: letters, numbers, dash, underscore, dot
        filename = re.sub(r'[^\w\-_\.]', '_', filename)
        # Prevent hidden files
        filename = filename.lstrip('.')
        # Enforce max length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:250] + ext
        # Prevent empty filename after sanitization
        if not filename or filename == '_':
            filename = 'upload_unnamed'
        return filename

    # ── Column Name Sanitization ──
    @staticmethod
    def sanitize_column_names(df) -> tuple:
        # Returns (sanitized_df, mapping_dict)
        # mapping_dict: {original_name: sanitized_name}
        import re
        import pandas as pd
        mapping = {}
        new_columns = []
        for col in df.columns:
            # Convert to string first
            col_str = str(col)
            # Remove SQL-dangerous characters
            sanitized = re.sub(r"['\";\\/*%$]", '', col_str)
            # Remove comment sequences
            sanitized = re.sub(r'--', '', sanitized)
            sanitized = re.sub(r'/\*', '', sanitized)
            sanitized = re.sub(r'\*/', '', sanitized)
            # Trim and limit length
            sanitized = sanitized.strip()[:100]
            # Ensure non-empty
            if not sanitized:
                sanitized = f'col_{len(new_columns)}'
            mapping[col_str] = sanitized
            new_columns.append(sanitized)
        df.columns = new_columns
        return df, mapping

    # ── Cell Value Sanitization for LLM prompts ──
    @staticmethod
    def sanitize_for_llm(text: str, max_length: int = 500) -> str:
        if not isinstance(text, str):
            text = str(text)
        # Detect and neutralize prompt injection patterns
        injection_patterns = [
            r'ignore\s+(all\s+)?(previous|prior|above)\s+instructions?',
            r'forget\s+(everything|all)',
            r'you\s+are\s+(now\s+)?(a|an)',
            r'new\s+instructions?:',
            r'system\s*prompt',
            r'disregard\s+(your\s+)?',
            r'act\s+as\s+(if\s+)?',
            r'pretend\s+(you\s+are|to\s+be)',
            r'jailbreak',
            r'dan\s+mode',
            r'developer\s+mode',
            r'do\s+anything\s+now',
        ]
        import re
        for pattern in injection_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return '[CONTENT_FILTERED]'
        # Truncate to max length
        if len(text) > max_length:
            text = text[:max_length] + '...[truncated]'
        return text

    # ── Auth Input Sanitization ──
    @staticmethod
    def sanitize_auth_input(value: str, field_type: str) -> str:
        if not isinstance(value, str):
            return ''
        value = value.strip()
        # Null byte removal
        value = value.replace('\x00', '')
        if field_type == 'email':
            # Lowercase, max 254 chars (RFC 5321)
            return value.lower()[:254]
        elif field_type == 'username':
            # Max 20 chars
            return value[:20]
        elif field_type == 'password':
            # Max 128 chars (prevent bcrypt DoS — bcrypt truncates at 72)
            return value[:128]
        return value[:1000]

    # ── Safe Email Regex (ReDoS-resistant) ──
    @staticmethod
    def validate_email_safe(email: str) -> bool:
        # Simple, linear-time regex — no catastrophic backtracking
        import re
        if len(email) > 254:
            return False
        # Split on @ manually — safer than complex regex
        parts = email.split('@')
        if len(parts) != 2:
            return False
        local, domain = parts
        if not local or not domain:
            return False
        if len(local) > 64:
            return False
        if '.' not in domain:
            return False
        # Simple character check only
        allowed = re.compile(r'^[\w.+\-]+$')
        return bool(allowed.match(local)) and bool(allowed.match(domain))
