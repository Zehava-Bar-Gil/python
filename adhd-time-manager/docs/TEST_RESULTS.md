# תוצאות הבדיקות

הורצו ב-29 באוקטובר 2026, Python 3.13.17, Flask 3.1.3, anthropic 2.3.0, על Linux.
הפקודה: `python -m unittest -v` מתיקיית הפרויקט.

**תוצאה: 150 בדיקות, כולן עברו (OK), ב-36 שניות בערך.**

כל הבדיקות משתמשות במסד זמני חדש, בשעון "קפוא" על 29.10.2026 10:00 שעון ישראל, ובנתונים סינתטיים בלבד.
אין פנייה לאינטרנט: Claude ו-Google מוחלפים באובייקטים מדומים, והמיילים נכתבים לתיקייה זמנית.

## מה נבדק

| קובץ | בדיקות | מה מכוסה |
|---|---|---|
| `test_auth.py` | 20 | הרשמה, hash של סיסמה, קלט לא תקין, מייל כפול, כניסה ויציאה, אותה הודעה לסיסמה שגויה ולמייל לא קיים, הגבלת ניסיונות ושחרור אחרי רבע שעה, מחיקת ניסיונות ישנים, הפניה לאתר זר נחסמת, כל הדפים דורשים התחברות, CSRF, כותרות אבטחה, דגלי עוגייה, שינוי סיסמה מנתק מכשירים אחרים, איפוס חד-פעמי ותפוגה, "שכחתי סיסמה" לא חושף אם מייל קיים, אימות מייל, מחיקת חשבון |
| `test_isolation.py` | 9 | משתמשת ב' לא רואה ולא משנה משימות, צעדים, פתקים, מחשבות, טיימר ואירועי יומן של משתמשת א'. הייצוא כולל רק את הנתונים שלה. מחיקת חשבון אחד לא פוגעת בשני |
| `test_tasks_notes.py` | 19 | משימות: יצירה עם כל השדות, ניקוי ערכים לא תקינים, כותרת ריקה, אורך מקסימלי, עריכה, סימון וביטול (נקודות), מחיקה, צעדים, סינון, הצעה לפרק, דחייה, **שמירה אחרי הפעלה מחדש**. פתקים: יצירה, עריכה, מחיקה, עברית ואנגלית, הפיכה למשימה, לצעד ול-Snooze |
| `test_timer_journey.py` | 21 | סשן פעיל אחד, סגירה בבקשה הבאה ונספר פעם אחת, השהיה והמשך, סשן מושהה לא נגמר, עצירה שומרת זמן, גמיש, הפסקות לפי ההגדרות, אימות דקות, הצעה להפסקה, הפסקה ארוכה אחרי 4, מצב מיקוד, צליל סיום רק כשמופעל, הצבעות צליל. מסע: חישוב תחנות, הכדור עולה, פסגה, הוספת משימות לא מורידה, פריט נספר פעם אחת, תחנות ביום |
| `test_personalization.py` | 23 | כל 4 הכללים וכל 6 הדפוסים עם היסטוריות סינתטיות, כולל מקרים שבהם אין מספיק תצפיות. בחירה של תובנה אחת, השהיה של 21 יום, "לא מדויק" לא חוזר. סקירה של 14 יום. נתיבים: למידה כבויה עד הסכמה, "לנסות" משנה את אורך המיקוד, "לא עכשיו", תובנה לא קיימת, כיבוי ומחיקת נתוני למידה, משתמשת ההדגמה |
| `test_pulse_mail.py` | 15 | Daily Pulse: שמירה עם סיבות תקינות בלבד, עריכה, דילוג, ערך לא תקין, מוצג רק בערב, כיבוי. קישור מהמייל עובד בלי התחברות ורק לשאלה שלו. סיכום יומי: נשלח פעם אחת אחרי השעה שנבחרה, נושא ניטרלי, נתונים אמיתיים בגוף, List-Unsubscribe, לא נשלח לכתובת לא מאומתת, ניסיון חוזר עם מגבלה, הסרה מרשימה, שליחה ידנית מוגבלת, מיילים של חשבון מוגבלים |
| `test_ai.py` | 17 | הצעה נשמרת ומוצגת, מייל וטלפון מוסתרים לפני שליחה, AI כבוי לא שולח כלום, שגיאה וסירוב נופלים למצב בסיסי בגלוי, מגבלה יומית, בלי מפתח, מספר הצעה לא קיים, הצעה מתחילה טיימר, "קשה להתחיל?" מוסיף צעדים, מיון והמרה, המפתח לא מופיע בדפים. ClaudeProvider עם לקוח מדומה: ניקוי תשובה, סירוב, JSON לא תקין, שגיאות 429/500/רשת. מצב בסיסי והסתרה |
| `test_calendar.py` | 11 | דף הסכמה והפניה ל-Google עם הרשאת קריאה בלבד, state לא תואם נדחה, חיבור וסנכרון, בלי כפילויות ומחיקה של אירוע שנמחק, הרשאה שבוטלה, חידוש אסימון, ניתוק מבטל ומוחק, אירוע הופך למשימה פעם אחת, מחיקת חשבון מנתקת, ניווט בחודשים, בלי מפתחות לא מוצג "מחובר" |
| `test_ui_db.py` | 15 | בדיוק 5 פריטים בתפריט העליון, **אין `<script>` ואין `onclick` באף דף**, דילוג לתוכן, לכל שדה יש תווית, ערכת צבעים, שפה, כיוון ותנועה, הגדרות נשמרות ומאומתות, טקסט זדוני מוצג כטקסט (XSS), מצב רגוע, יעד, החלפת שפה, דף 404. מסד: מיגרציה חוזרת, גיבוי ושחזור, מגבלות במסד, תקלה במסד מציגה דף רגוע בלי פרטים טכניים |

## באגים שהבדיקות מצאו ותוקנו

| באג | תיקון |
|---|---|
| הסיכום היומי שנשלח מתהליך הרקע קרס, כי התבנית ניסתה לקרוא את כתובת הבקשה כשאין בקשה | `is_timeflow_request()` מחזיר False כשאין בקשה (`has_request_context`) |
| ב-Windows, תיקיות הבדיקה הזמניות היו נשארות, כי המחיקה רצה לפני סגירת החיבורים למסד | סדר הניקוי בבדיקות הוחלף |

## בדיקות ידניות (בדפדפן Chromium דרך Playwright)

- השרת האמיתי (`python app.py`) עולה, וכל הדפים מחזירים 200. `/` ו-`/api/health` של השלד עובדים.
- `init-db`, `seed-demo` ו-`backup-db` רצו בהצלחה על התקנה נקייה.
- צילומי מסך במצב בהיר, כהה וטלפון (390 פיקסלים): ב-[screenshots/](screenshots/). בטלפון אין גלילה לרוחב באף דף שנבדק.

## מה לא נבדק

- קריאה אמיתית ל-Claude API, שליחת SMTP אמיתית, וחיבור אמיתי ל-Google. כל אלה צריכים מפתחות, ונבדקו מול שירותים מדומים בלבד.
- קורא מסך אמיתי (NVDA או VoiceOver). נבדקו רק המבנה, התוויות וה-ARIA.
- דפדפנים אחרים מלבד Chromium.

## הפלט המלא

```
test_api_errors_become_provider_errors (tests.test_ai.ClaudeProviderTests.test_api_errors_become_provider_errors) ... ok
test_offline_provider (tests.test_ai.ClaudeProviderTests.test_offline_provider) ... ok
test_refusal_and_bad_output (tests.test_ai.ClaudeProviderTests.test_refusal_and_bad_output) ... ok
test_scrub (tests.test_ai.ClaudeProviderTests.test_scrub) ... ok
test_valid_answer_is_cleaned (tests.test_ai.ClaudeProviderTests.test_valid_answer_is_cleaned) ... ok
test_api_key_never_reaches_the_page (tests.test_ai.SnoozeAiTests.test_api_key_never_reaches_the_page) ... ok
test_daily_limit (tests.test_ai.SnoozeAiTests.test_daily_limit) ... ok
test_disabled_by_user_uses_basic_mode_without_calling (tests.test_ai.SnoozeAiTests.test_disabled_by_user_uses_basic_mode_without_calling) ... ok
test_option_index_is_read_from_server (tests.test_ai.SnoozeAiTests.test_option_index_is_read_from_server) ... ok
test_option_starts_timer_with_its_minutes (tests.test_ai.SnoozeAiTests.test_option_starts_timer_with_its_minutes) ... ok
test_personal_details_are_removed_before_sending (tests.test_ai.SnoozeAiTests.test_personal_details_are_removed_before_sending) ... ok
test_provider_error_falls_back_honestly (tests.test_ai.SnoozeAiTests.test_provider_error_falls_back_honestly) ... ok
test_refusal_falls_back (tests.test_ai.SnoozeAiTests.test_refusal_falls_back) ... ok
test_sort_convert_and_delete (tests.test_ai.SnoozeAiTests.test_sort_convert_and_delete) ... ok
test_start_help_adds_steps_to_the_original_task (tests.test_ai.SnoozeAiTests.test_start_help_adds_steps_to_the_original_task) ... ok
test_suggestion_from_provider_is_saved_and_shown (tests.test_ai.SnoozeAiTests.test_suggestion_from_provider_is_saved_and_shown) ... ok
test_without_key_the_page_says_basic_mode (tests.test_ai.SnoozeAiTests.test_without_key_the_page_says_basic_mode) ... ok
test_delete_account_removes_all_data (tests.test_auth.AccountDeletionTests.test_delete_account_removes_all_data) ... ok
test_other_paths_get_json_errors (tests.test_auth.CsrfAndHeadersTests.test_other_paths_get_json_errors) ... ok
test_post_without_csrf_token_is_rejected (tests.test_auth.CsrfAndHeadersTests.test_post_without_csrf_token_is_rejected) ... ok
test_security_headers (tests.test_auth.CsrfAndHeadersTests.test_security_headers) ... ok
test_session_cookie_flags (tests.test_auth.CsrfAndHeadersTests.test_session_cookie_flags) ... ok
test_login_and_logout (tests.test_auth.LoginTests.test_login_and_logout) ... ok
test_next_parameter_cannot_redirect_outside (tests.test_auth.LoginTests.test_next_parameter_cannot_redirect_outside) ... ok
test_old_login_attempts_are_deleted (tests.test_auth.LoginTests.test_old_login_attempts_are_deleted) ... ok
test_pages_require_login (tests.test_auth.LoginTests.test_pages_require_login) ... ok
test_rate_limit_after_five_failures (tests.test_auth.LoginTests.test_rate_limit_after_five_failures) ... ok
test_wrong_password_same_message_as_unknown_email (tests.test_auth.LoginTests.test_wrong_password_same_message_as_unknown_email) ... ok
test_change_password_logs_out_other_sessions (tests.test_auth.PasswordAndTokenTests.test_change_password_logs_out_other_sessions) ... ok
test_forgot_does_not_reveal_accounts (tests.test_auth.PasswordAndTokenTests.test_forgot_does_not_reveal_accounts) ... ok
test_reset_token_expires (tests.test_auth.PasswordAndTokenTests.test_reset_token_expires) ... ok
test_reset_token_works_once (tests.test_auth.PasswordAndTokenTests.test_reset_token_works_once) ... ok
test_verify_email_link (tests.test_auth.PasswordAndTokenTests.test_verify_email_link) ... ok
test_duplicate_email_is_rejected_case_insensitive (tests.test_auth.RegistrationTests.test_duplicate_email_is_rejected_case_insensitive) ... ok
test_register_logs_in_and_hashes_password (tests.test_auth.RegistrationTests.test_register_logs_in_and_hashes_password) ... ok
test_register_rejects_bad_input (tests.test_auth.RegistrationTests.test_register_rejects_bad_input) ... ok
test_verification_email_written_to_outbox (tests.test_auth.RegistrationTests.test_verification_email_written_to_outbox) ... ok
test_account_deletion_disconnects_google (tests.test_calendar.CalendarTests.test_account_deletion_disconnects_google) ... ok
test_connect_syncs_events (tests.test_calendar.CalendarTests.test_connect_syncs_events) ... ok
test_consent_page_then_redirect_to_google (tests.test_calendar.CalendarTests.test_consent_page_then_redirect_to_google) ... ok
test_disconnect_revokes_and_deletes (tests.test_calendar.CalendarTests.test_disconnect_revokes_and_deletes) ... ok
test_event_becomes_task_once (tests.test_calendar.CalendarTests.test_event_becomes_task_once) ... ok
test_expired_token_is_refreshed (tests.test_calendar.CalendarTests.test_expired_token_is_refreshed) ... ok
test_month_navigation (tests.test_calendar.CalendarTests.test_month_navigation) ... ok
test_revoked_access_shows_reconnect (tests.test_calendar.CalendarTests.test_revoked_access_shows_reconnect) ... ok
test_sync_again_has_no_duplicates_and_removes_deleted (tests.test_calendar.CalendarTests.test_sync_again_has_no_duplicates_and_removes_deleted) ... ok
test_wrong_state_is_rejected (tests.test_calendar.CalendarTests.test_wrong_state_is_rejected) ... ok
test_without_keys_nothing_pretends_to_be_connected (tests.test_calendar.NotConfiguredTests.test_without_keys_nothing_pretends_to_be_connected) ... ok
test_calendar_event_of_other_user (tests.test_isolation.IsolationTests.test_calendar_event_of_other_user) ... ok
test_deleting_one_account_keeps_the_other (tests.test_isolation.IsolationTests.test_deleting_one_account_keeps_the_other) ... ok
test_export_contains_only_own_data (tests.test_isolation.IsolationTests.test_export_contains_only_own_data) ... ok
test_note_cannot_become_step_of_other_users_task (tests.test_isolation.IsolationTests.test_note_cannot_become_step_of_other_users_task) ... ok
test_note_routes_return_404_for_other_user (tests.test_isolation.IsolationTests.test_note_routes_return_404_for_other_user) ... ok
test_pages_do_not_show_other_users_data (tests.test_isolation.IsolationTests.test_pages_do_not_show_other_users_data) ... ok
test_snooze_routes_return_404_for_other_user (tests.test_isolation.IsolationTests.test_snooze_routes_return_404_for_other_user) ... ok
test_task_routes_return_404_for_other_user (tests.test_isolation.IsolationTests.test_task_routes_return_404_for_other_user) ... ok
test_timer_cannot_attach_other_users_task (tests.test_isolation.IsolationTests.test_timer_cannot_attach_other_users_task) ... ok
test_corrected_never_returns (tests.test_personalization.ChoiceTests.test_corrected_never_returns) ... ok
test_dismissed_waits_21_days (tests.test_personalization.ChoiceTests.test_dismissed_waits_21_days) ... ok
test_one_insight_strongest_first (tests.test_personalization.ChoiceTests.test_one_insight_strongest_first) ... ok
test_overview (tests.test_personalization.ChoiceTests.test_overview) ... ok
test_consent_and_accept_changes_focus_length (tests.test_personalization.LearningRouteTests.test_consent_and_accept_changes_focus_length) ... ok
test_demo_seed_produces_a_working_history (tests.test_personalization.LearningRouteTests.test_demo_seed_produces_a_working_history) ... ok
test_dismiss_hides_the_suggestion (tests.test_personalization.LearningRouteTests.test_dismiss_hides_the_suggestion) ... ok
test_learning_is_off_until_consent (tests.test_personalization.LearningRouteTests.test_learning_is_off_until_consent) ... ok
test_turning_off_and_deleting_learning_data (tests.test_personalization.LearningRouteTests.test_turning_off_and_deleting_learning_data) ... ok
test_unknown_or_inactive_insight_is_ignored (tests.test_personalization.LearningRouteTests.test_unknown_or_inactive_insight_is_ignored) ... ok
test_breaks_return (tests.test_personalization.PatternTests.test_breaks_return) ... ok
test_focus_length_suggests_direction (tests.test_personalization.PatternTests.test_focus_length_suggests_direction) ... ok
test_planning_load (tests.test_personalization.PatternTests.test_planning_load) ... ok
test_small_start (tests.test_personalization.PatternTests.test_small_start) ... ok
test_sound_helped_and_opt_out (tests.test_personalization.PatternTests.test_sound_helped_and_opt_out) ... ok
test_steps_start (tests.test_personalization.PatternTests.test_steps_start) ... ok
test_empty_history_gives_nothing (tests.test_personalization.RuleTests.test_empty_history_gives_nothing) ... ok
test_hard_start (tests.test_personalization.RuleTests.test_hard_start) ... ok
test_overloaded_uses_last_five_answers (tests.test_personalization.RuleTests.test_overloaded_uses_last_five_answers) ... ok
test_short_sessions_needs_enough_observations (tests.test_personalization.RuleTests.test_short_sessions_needs_enough_observations) ... ok
test_short_sessions_rule (tests.test_personalization.RuleTests.test_short_sessions_rule) ... ok
test_short_sessions_skipped_when_already_short (tests.test_personalization.RuleTests.test_short_sessions_skipped_when_already_short) ... ok
test_split_postponed_points_to_most_postponed (tests.test_personalization.RuleTests.test_split_postponed_points_to_most_postponed) ... ok
test_account_emails_are_limited (tests.test_pulse_mail.DailyEmailTests.test_account_emails_are_limited) ... ok
test_failed_send_is_retried_later_with_a_limit (tests.test_pulse_mail.DailyEmailTests.test_failed_send_is_retried_later_with_a_limit) ... ok
test_failed_send_succeeds_on_retry (tests.test_pulse_mail.DailyEmailTests.test_failed_send_succeeds_on_retry) ... ok
test_manual_send_needs_verified_address_and_is_limited (tests.test_pulse_mail.DailyEmailTests.test_manual_send_needs_verified_address_and_is_limited) ... ok
test_not_sent_to_unverified_or_disabled (tests.test_pulse_mail.DailyEmailTests.test_not_sent_to_unverified_or_disabled) ... ok
test_sent_once_after_chosen_time (tests.test_pulse_mail.DailyEmailTests.test_sent_once_after_chosen_time) ... ok
test_subject_is_neutral_and_body_has_real_data (tests.test_pulse_mail.DailyEmailTests.test_subject_is_neutral_and_body_has_real_data) ... ok
test_unsubscribe_confirm_then_post (tests.test_pulse_mail.DailyEmailTests.test_unsubscribe_confirm_then_post) ... ok
test_edit_keeps_one_answer_per_day (tests.test_pulse_mail.PulseTests.test_edit_keeps_one_answer_per_day) ... ok
test_email_link_works_without_login_for_that_day (tests.test_pulse_mail.PulseTests.test_email_link_works_without_login_for_that_day) ... ok
test_home_asks_only_in_the_evening (tests.test_pulse_mail.PulseTests.test_home_asks_only_in_the_evening) ... ok
test_pulse_can_be_turned_off (tests.test_pulse_mail.PulseTests.test_pulse_can_be_turned_off) ... ok
test_save_rating_with_valid_reasons_only (tests.test_pulse_mail.PulseTests.test_save_rating_with_valid_reasons_only) ... ok
test_skip_and_invalid (tests.test_pulse_mail.PulseTests.test_skip_and_invalid) ... ok
test_tampered_or_wrong_purpose_token (tests.test_pulse_mail.PulseTests.test_tampered_or_wrong_purpose_token) ... ok
test_add_edit_delete_note (tests.test_tasks_notes.NoteTests.test_add_edit_delete_note) ... ok
test_empty_note_is_not_saved (tests.test_tasks_notes.NoteTests.test_empty_note_is_not_saved) ... ok
test_hebrew_and_english_note_render (tests.test_tasks_notes.NoteTests.test_hebrew_and_english_note_render) ... ok
test_note_to_snooze (tests.test_tasks_notes.NoteTests.test_note_to_snooze) ... ok
test_note_to_step (tests.test_tasks_notes.NoteTests.test_note_to_step) ... ok
test_note_to_task (tests.test_tasks_notes.NoteTests.test_note_to_task) ... ok
test_add_task_with_all_fields (tests.test_tasks_notes.TaskTests.test_add_task_with_all_fields) ... ok
test_data_survives_new_app_instance (tests.test_tasks_notes.TaskTests.test_data_survives_new_app_instance) ... ok
test_delete_keeps_points_already_earned (tests.test_tasks_notes.TaskTests.test_delete_keeps_points_already_earned) ... ok
test_deleting_task_deletes_its_steps (tests.test_tasks_notes.TaskTests.test_deleting_task_deletes_its_steps) ... ok
test_edit_task (tests.test_tasks_notes.TaskTests.test_edit_task) ... ok
test_empty_title_is_not_saved (tests.test_tasks_notes.TaskTests.test_empty_title_is_not_saved) ... ok
test_filter_and_progressive_list (tests.test_tasks_notes.TaskTests.test_filter_and_progressive_list) ... ok
test_invalid_values_are_cleaned (tests.test_tasks_notes.TaskTests.test_invalid_values_are_cleaned) ... ok
test_long_title_is_cut (tests.test_tasks_notes.TaskTests.test_long_title_is_cut) ... ok
test_postpone_next_timed_task (tests.test_tasks_notes.TaskTests.test_postpone_next_timed_task) ... ok
test_split_hint_after_three_postpones (tests.test_tasks_notes.TaskTests.test_split_hint_after_three_postpones) ... ok
test_steps (tests.test_tasks_notes.TaskTests.test_steps) ... ok
test_toggle_awards_and_unawards_points (tests.test_tasks_notes.TaskTests.test_toggle_awards_and_unawards_points) ... ok
test_adding_tasks_never_lowers_progress (tests.test_timer_journey.JourneyTests.test_adding_tasks_never_lowers_progress) ... ok
test_balloon_moves_up_with_points (tests.test_timer_journey.JourneyTests.test_balloon_moves_up_with_points) ... ok
test_position_math (tests.test_timer_journey.JourneyTests.test_position_math) ... ok
test_same_item_counts_once (tests.test_timer_journey.JourneyTests.test_same_item_counts_once) ... ok
test_stations_reached_per_day (tests.test_timer_journey.JourneyTests.test_stations_reached_per_day) ... ok
test_view_remembers_what_was_shown_and_celebrates_summit (tests.test_timer_journey.JourneyTests.test_view_remembers_what_was_shown_and_celebrates_summit) ... ok
test_break_offer_after_focus (tests.test_timer_journey.TimerTests.test_break_offer_after_focus) ... ok
test_breaks_use_settings_length_and_give_no_points (tests.test_timer_journey.TimerTests.test_breaks_use_settings_length_and_give_no_points) ... ok
test_chime_plays_only_when_enabled (tests.test_timer_journey.TimerTests.test_chime_plays_only_when_enabled) ... ok
test_flexible_session (tests.test_timer_journey.TimerTests.test_flexible_session) ... ok
test_focus_mode_done_marks_task (tests.test_timer_journey.TimerTests.test_focus_mode_done_marks_task) ... ok
test_lazy_completion_is_counted_once (tests.test_timer_journey.TimerTests.test_lazy_completion_is_counted_once) ... ok
test_leaving_focus_mode_keeps_time (tests.test_timer_journey.TimerTests.test_leaving_focus_mode_keeps_time) ... ok
test_long_break_after_four_sessions (tests.test_timer_journey.TimerTests.test_long_break_after_four_sessions) ... ok
test_minutes_are_validated (tests.test_timer_journey.TimerTests.test_minutes_are_validated) ... ok
test_only_one_active_session (tests.test_timer_journey.TimerTests.test_only_one_active_session) ... ok
test_pause_and_resume (tests.test_timer_journey.TimerTests.test_pause_and_resume) ... ok
test_paused_session_does_not_finish (tests.test_timer_journey.TimerTests.test_paused_session_does_not_finish) ... ok
test_reset_records_real_time_without_points (tests.test_timer_journey.TimerTests.test_reset_records_real_time_without_points) ... ok
test_sound_votes (tests.test_timer_journey.TimerTests.test_sound_votes) ... ok
test_very_short_flexible_session_is_not_counted (tests.test_timer_journey.TimerTests.test_very_short_flexible_session_is_not_counted) ... ok
test_backup_and_restore (tests.test_ui_db.DatabaseTests.test_backup_and_restore) ... ok
test_constraints_protect_data (tests.test_ui_db.DatabaseTests.test_constraints_protect_data) ... ok
test_database_error_shows_calm_page (tests.test_ui_db.DatabaseTests.test_database_error_shows_calm_page) ... ok
test_migrate_is_idempotent (tests.test_ui_db.DatabaseTests.test_migrate_is_idempotent) ... ok
test_calm_mode_hides_the_planning_board (tests.test_ui_db.InterfaceTests.test_calm_mode_hides_the_planning_board) ... ok
test_every_page_has_skip_link_and_main (tests.test_ui_db.InterfaceTests.test_every_page_has_skip_link_and_main) ... ok
test_exactly_five_items_in_top_nav (tests.test_ui_db.InterfaceTests.test_exactly_five_items_in_top_nav) ... ok
test_goal_text (tests.test_ui_db.InterfaceTests.test_goal_text) ... ok
test_inputs_have_labels (tests.test_ui_db.InterfaceTests.test_inputs_have_labels) ... ok
test_language_switch (tests.test_ui_db.InterfaceTests.test_language_switch) ... ok
test_no_javascript_on_any_page (tests.test_ui_db.InterfaceTests.test_no_javascript_on_any_page) ... ok
test_not_found_page (tests.test_ui_db.InterfaceTests.test_not_found_page) ... ok
test_settings_form_saves_and_validates (tests.test_ui_db.InterfaceTests.test_settings_form_saves_and_validates) ... ok
test_theme_language_and_motion (tests.test_ui_db.InterfaceTests.test_theme_language_and_motion) ... ok
test_user_text_is_escaped (tests.test_ui_db.InterfaceTests.test_user_text_is_escaped) ... ok

Ran 150 tests in 34.599s

OK
```
