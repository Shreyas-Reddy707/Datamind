class UploadGuard:

    ALLOWED_EXTENSIONS = {'.csv', '.xlsx', '.xls', '.json', '.parquet'}
    ALLOWED_MIMETYPES = {
        'text/csv', 'application/csv',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/json',
        'application/octet-stream',  # parquet
    }
    MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
    MAX_ROWS_SAFE = 500_000
    MAX_COLS_SAFE = 500
    # Excel bomb limits
    MAX_EXCEL_ROWS = 100_000
    MAX_EXCEL_COLS = 200

    @staticmethod
    def validate_before_read(file_bytes: bytes, filename: str) -> dict:
        import os

        # 1. Extension check
        ext = os.path.splitext(filename)[1].lower()
        if ext not in UploadGuard.ALLOWED_EXTENSIONS:
            return {"safe": False,
                    "error": f"File type '{ext}' not allowed. Supported: {', '.join(UploadGuard.ALLOWED_EXTENSIONS)}"}

        # 2. File size check (before reading content)
        if len(file_bytes) > UploadGuard.MAX_FILE_SIZE_BYTES:
            mb = len(file_bytes) / (1024*1024)
            return {"safe": False,
                    "error": f"File too large ({mb:.1f}MB). Maximum: {(UploadGuard.MAX_FILE_SIZE_BYTES // (1024*1024))}MB"}

        # 3. Magic bytes check (verify real file type, not just extension)
        magic_checks = {
            '.xlsx': b'PK\x03\x04',       # ZIP-based format
            '.xls': b'\xd0\xcf\x11\xe0',  # OLE2 format
            '.parquet': b'PAR1',
        }
        if ext in magic_checks:
            expected_magic = magic_checks[ext]
            if not file_bytes.startswith(expected_magic):
                return {"safe": False,
                        "error": "File content does not match its extension. Upload rejected for security reasons."}

        # 4. Null byte check (binary injection attempt)
        if b'\x00' in file_bytes[:1024] and ext == '.csv':
            return {"safe": False,
                    "error": "Invalid file content detected."}

        return {"safe": True, "error": None}

    @staticmethod
    def validate_after_read(df, filename: str) -> dict:
        import os
        ext = os.path.splitext(filename)[1].lower()

        # 1. Row count check
        if len(df) > UploadGuard.MAX_ROWS_SAFE:
            return {"safe": False,
                    "error": f"File has {len(df):,} rows. Maximum: {UploadGuard.MAX_ROWS_SAFE:,}"}

        # 2. Column count check (zip bomb via columns)
        if len(df.columns) > UploadGuard.MAX_COLS_SAFE:
            return {"safe": False,
                    "error": f"File has {len(df.columns)} columns. Maximum: {UploadGuard.MAX_COLS_SAFE}"}

        # 3. Excel-specific bomb check
        if ext in ('.xlsx', '.xls'):
            if len(df) > UploadGuard.MAX_EXCEL_ROWS:
                return {"safe": False,
                        "error": f"Excel file exceeds {UploadGuard.MAX_EXCEL_ROWS:,} row limit for safety."}

        # 4. Memory size estimate check
        try:
            mem_mb = df.memory_usage(deep=True).sum() / (1024*1024)
            if mem_mb > 500:
                return {"safe": False,
                        "error": f"Dataset uses ~{mem_mb:.0f}MB in memory. Maximum: 500MB"}
        except Exception:
            pass

        return {"safe": True, "error": None}
