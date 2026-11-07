class SecurityError(Exception):
    pass

class Authorizer:

    @staticmethod
    def user_owns_file(user_id: int, global_file_id: int) -> bool:
        import database as db
        result = db.get_user_file_ref(user_id, global_file_id)
        return result is not None

    @staticmethod
    def user_owns_analysis(user_id: int, analysis_id: int) -> bool:
        import database as db
        with db.get_db_connection() as conn:
            row = conn.execute("""
                SELECT id FROM analysis_memory
                WHERE id = ? AND user_id = ?
            """, (analysis_id, user_id)).fetchone()
        return row is not None

    @staticmethod
    def user_owns_prediction(user_id: int, prediction_id: int) -> bool:
        import database as db
        with db.get_db_connection() as conn:
            row = conn.execute("""
                SELECT id FROM prediction_history
                WHERE id = ? AND user_id = ?
            """, (prediction_id, user_id)).fetchone()
        return row is not None

    @staticmethod
    def assert_file_access(user_id: int, global_file_id: int):
        import database as db
        if user_id is None:
            raise SecurityError("Authentication required")
        if not Authorizer.user_owns_file(user_id, global_file_id):
            db.log_event(user_id, 'unauthorized_access_attempt',
                        f"Tried to access file_id={global_file_id}")
            raise SecurityError("Access denied")
