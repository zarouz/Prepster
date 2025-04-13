# auth.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
# Import db and models, bcrypt from models.py
from models import db, User, PasswordReset, bcrypt
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from email_validator import validate_email, EmailNotValidError
import datetime
from flask_mail import Message # Import Message for email

# Import mail object and serializers from app context
from flask import current_app as app # Use app context

# Define Blueprint
auth_bp = Blueprint('auth', __name__, template_folder='templates/auth')

# --- Helper Functions (send_email, generate/confirm email token) ---
def send_email(to, subject, template):
    try:
        # Ensure mail is initialized in the app context
        mail = app.extensions.get('mail')
        if not mail:
            app.logger.error("Flask-Mail extension not found or initialized.")
            return False

        msg = Message(
            subject,
            recipients=[to],
            html=template,
            sender=app.config['MAIL_DEFAULT_SENDER']
        )
        mail.send(msg)
        app.logger.info(f"Email sent successfully to {to} with subject '{subject}'")
        return True
    except Exception as e:
        app.logger.error(f"Error sending email to {to}: {e}", exc_info=True)
        return False

# --- Email Confirmation Token Helpers (Modified for Invalidation) ---
def generate_confirmation_token(user):
    """Generates a confirmation token containing email and the current sent timestamp."""
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    # Update the timestamp on the user object *before* generating the token
    user.confirmation_sent_at = datetime.datetime.now(datetime.timezone.utc)
    # Include both email and the timestamp in the token data
    token_data = {'email': user.email, 'ts': user.confirmation_sent_at.isoformat()}
    return serializer.dumps(token_data, salt=app.config['EMAIL_CONFIRMATION_SALT'])

def confirm_token(token, expiration=None):
    """Confirms a token, checking email and timestamp against the user record."""
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    expiration = expiration or app.config['EMAIL_TOKEN_EXPIRATION']
    try:
        token_data = serializer.loads(
            token,
            salt=app.config['EMAIL_CONFIRMATION_SALT'],
            max_age=expiration
        )
        email = token_data.get('email')
        token_ts_str = token_data.get('ts')

        if not email or not token_ts_str:
            app.logger.warning("Confirmation token data missing email or timestamp.")
            return None # Indicate invalid data

        # Find the user by email
        user = User.query.filter_by(email=email).first()
        if not user:
            app.logger.warning(f"Confirmation token validation failed: User not found for email {email}")
            return None # User not found

        # Compare the timestamp from the token with the one stored in the database
        # Convert token timestamp string back to datetime object for comparison
        try:
            token_ts = datetime.datetime.fromisoformat(token_ts_str)
        except ValueError:
            app.logger.warning(f"Confirmation token validation failed: Invalid timestamp format in token for {email}")
            return None # Invalid timestamp format

        # Ensure user.confirmation_sent_at is not None and is timezone-aware for comparison
        if user.confirmation_sent_at is None:
             app.logger.warning(f"Confirmation token validation failed: User {email} has no confirmation_sent_at timestamp.")
             return None

        # Make user timestamp timezone-aware if it isn't (assuming UTC if naive)
        user_ts = user.confirmation_sent_at
        if user_ts.tzinfo is None:
            user_ts = user_ts.replace(tzinfo=datetime.timezone.utc)

        # Compare timestamps (allow for minor clock skew, e.g., 1 second)
        if abs((token_ts - user_ts).total_seconds()) > 1:
            app.logger.warning(f"Confirmation token validation failed: Timestamp mismatch for {email}. Token TS: {token_ts}, DB TS: {user_ts}")
            return None # Timestamps don't match, token is outdated

        # If timestamps match, return the user object (more useful than just email)
        return user

    except (SignatureExpired, BadTimeSignature):
         app.logger.warning(f"Confirmation token expired or invalid signature: {token[:10]}...")
         return None # Indicate expired/invalid signature
    except Exception as e:
        app.logger.error(f"Error confirming token: {e}", exc_info=True)
        return False

# --- Password Reset Token Helpers (Modified) ---
def generate_password_reset_itsdangerous_token(user_id):
     serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
     return serializer.dumps(str(user_id), salt=app.config['SECURITY_PASSWORD_SALT'])

def verify_password_reset_itsdangerous_token(token, expiration=None):
     serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
     expiration = expiration or app.config['PASSWORD_RESET_TOKEN_EXPIRATION']
     try:
         user_id = serializer.loads(
             token,
             salt=app.config['SECURITY_PASSWORD_SALT'],
             max_age=expiration
         )
         return int(user_id) # Return user ID if valid and not expired
     except (SignatureExpired, BadTimeSignature):
         app.logger.debug(f"Password reset token expired or invalid signature: {token[:10]}...")
         return None # Indicates expired or invalid signature
     except Exception as e:
         app.logger.error(f"Error verifying password reset token: {e}", exc_info=True)
         return None


# --- Routes ---
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('interview_page'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        error = None

        # --- Validation ---
        if not username or not email or not password or not confirm_password:
            error = 'All fields are required.'
        elif len(password) < 8:
             error = 'Password must be at least 8 characters long.'
        elif password != confirm_password:
            error = 'Passwords do not match.'
        else:
            try:
                valid = validate_email(email, check_deliverability=False) # Basic format check
                email = valid.normalized # Use normalized email
            except EmailNotValidError as e:
                error = f"Invalid email address: {e}"

        if error is None:
            # --- Check Uniqueness ---
            existing_user_email = User.query.filter_by(email=email).first()
            existing_user_username = User.query.filter(User.username.ilike(username)).first() # Case-insensitive check

            if existing_user_email:
                error = f'Email address "{email}" is already registered.'
            elif existing_user_username:
                error = f'Username "{username}" is already taken.'

        if error is None:
            # --- Create User & Send Confirmation ---
            try:
                new_user = User(username=username, email=email, password=password, is_confirmed=False)
                db.session.add(new_user)
                # Commit the user first to get an ID and ensure it exists
                db.session.add(new_user)
                db.session.flush() # Assigns ID without ending transaction

                # Generate token *after* user is flushed, passing the user object
                token = generate_confirmation_token(new_user)
                # Commit the transaction *including* the updated confirmation_sent_at
                db.session.commit()
                app.logger.info(f"User '{username}' ({email}) created, confirmation_sent_at updated, awaiting confirmation.")

                confirm_url = url_for('auth.confirm_email', token=token, _external=True)
                html = render_template('email/confirm_email.html', confirm_url=confirm_url)
                subject = "Please confirm your email address"

                if send_email(new_user.email, subject, html):
                    flash('Registration successful! A confirmation email has been sent. Please check your inbox.', 'success')
                    return redirect(url_for('auth.login'))
                else:
                    # Important: Rollback user creation if email fails, otherwise user exists but can't confirm
                    db.session.rollback()
                    app.logger.error(f"Email sending failed for {email} during registration. User creation rolled back.")
                    flash('Registration failed: Could not send confirmation email. Please try again later or contact support.', 'danger')
                    # No need to set 'error' variable here, flash message is shown

            except Exception as e:
                 db.session.rollback() # Rollback on any DB error
                 app.logger.error(f"Error during registration for '{username}': {e}", exc_info=True)
                 flash(f'An unexpected error occurred during registration. Please try again.', 'danger')
                 # No need to set 'error' variable here

        # If validation or uniqueness checks failed
        if error:
            flash(error, 'danger')

    # Show form for GET or if POST had errors
    return render_template('register.html')


@auth_bp.route('/confirm/<token>')
def confirm_email(token):
    user = confirm_token(token) # Now returns user object or None

    if not user:
         flash('The confirmation link is invalid, has expired, or is outdated.', 'danger')
         return redirect(url_for('auth.login'))

    # User object is already fetched by confirm_token if valid

    if user.is_confirmed:
        flash('Your account is already confirmed. Please login.', 'info')
    else:
        try:
            user.is_confirmed = True
            db.session.commit()
            flash('Your account has been confirmed successfully! You can now log in.', 'success')
            app.logger.info(f"User '{user.username}' confirmed email successfully.")
            # Optional: Log the user in automatically after confirmation
            # login_user(user)
            # return redirect(url_for('interview_page'))
        except Exception as e:
             db.session.rollback()
             app.logger.error(f"Error updating user confirmation status for {email}: {e}", exc_info=True)
             flash('An error occurred during account confirmation. Please contact support.', 'danger')

    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('interview_page'))

    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password')
        remember = True if request.form.get('remember') == 'y' else False # Check for 'y' value
        error = None

        if not email or not password:
            error = 'Email and password are required.'
        else:
            user = User.query.filter_by(email=email).first()

            if not user:
                error = 'Invalid email or password.' # Generic message for security
                app.logger.warning(f"Login failed: Email not found - {email}")
            elif user.is_locked:
                error = 'Account locked due to too many failed attempts. Please reset your password.'
                app.logger.warning(f"Login failed: Account locked - {email}")
            elif not user.is_confirmed:
                 error = 'Account not confirmed. Please check your email for the confirmation link.'
                 app.logger.warning(f"Login failed: Account not confirmed - {email}")
                 # Add resend logic here if desired
            elif not user.check_password(password):
                error = 'Invalid email or password.' # Generic message
                try:
                    user.failed_attempts = (user.failed_attempts or 0) + 1
                    app.logger.warning(f"Login failed: Incorrect password attempt {user.failed_attempts}/{app.config['FAILED_LOGIN_ATTEMPTS_LOCKOUT']} for {email}")
                    if user.failed_attempts >= app.config['FAILED_LOGIN_ATTEMPTS_LOCKOUT']:
                        user.is_locked = True
                        error = 'Account locked due to too many failed attempts. Please reset your password.'
                        app.logger.warning(f"Account locked for user {email}.")
                    # else:
                         # Optionally flash remaining attempts, but can be annoying
                         # remaining = app.config['FAILED_LOGIN_ATTEMPTS_LOCKOUT'] - user.failed_attempts
                         # flash(f'{remaining} login attempts remaining.', 'warning')
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"Error updating failed attempts for {email}: {e}", exc_info=True)
                    error = "An error occurred during login processing." # Overwrite generic error
            else:
                # --- Login Successful ---
                try:
                    user.failed_attempts = 0
                    user.is_locked = False # Ensure unlocked
                    db.session.commit()
                    login_user(user, remember=remember)
                    app.logger.info(f"User '{user.username}' logged in successfully.")
                    next_page = request.args.get('next')
                    # Basic validation for next_page to prevent open redirect
                    if next_page and not next_page.startswith('/'):
                        next_page = url_for('interview_page') # Default if next is suspicious
                    return redirect(next_page or url_for('interview_page'))
                except Exception as e:
                     db.session.rollback()
                     app.logger.error(f"Error updating user status on successful login for {email}: {e}", exc_info=True)
                     error = "An error occurred finalizing login."

        # If validation or login checks failed
        if error:
            flash(error, 'danger')

    # Show form for GET or if POST had errors
    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    username = current_user.username # Get username before logging out
    logout_user()
    flash('You have been logged out successfully.', 'success')
    app.logger.info(f"User '{username}' logged out.")
    return redirect(url_for('auth.login'))


@auth_bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('interview_page'))

    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        user = User.query.filter_by(email=email).first()
        processed = False # Flag to know if we attempted processing

        if user:
            processed = True # Found a user matching the email
            if not user.is_confirmed:
                flash('Your account must be confirmed before resetting the password.', 'warning')
                app.logger.info(f"Password reset requested for unconfirmed account: {email}")
                # Don't proceed further for unconfirmed account
            else:
                # Account is confirmed, proceed with reset logic
                try:
                    # Invalidate previous tokens by deleting records
                    PasswordReset.query.filter_by(user_id=user.id).delete()

                    # Generate new token and expiry
                    raw_token = generate_password_reset_itsdangerous_token(user.id)
                    expiry_duration = datetime.timedelta(seconds=app.config['PASSWORD_RESET_TOKEN_EXPIRATION'])
                    # Ensure expiry is timezone-aware if needed (using UTC here)
                    expires_at = datetime.datetime.now(datetime.timezone.utc) + expiry_duration

                    # Create DB record with hashed token
                    new_reset_request = PasswordReset(user_id=user.id, token=raw_token, expires_at=expires_at)
                    db.session.add(new_reset_request)
                    db.session.commit()

                    # Send email
                    reset_url = url_for('auth.reset_password', token=raw_token, _external=True)
                    html = render_template('email/reset_password.html', reset_url=reset_url)
                    subject = "Password Reset Request"

                    if send_email(user.email, subject, html):
                        flash('Password reset instructions have been sent to your email.', 'success')
                        app.logger.info(f"Password reset email sent successfully for user {user.email}")
                    else:
                        db.session.rollback() # Rollback DB record if email fails
                        app.logger.error(f"Failed to send password reset email to {user.email}. Reset record rolled back.")
                        flash('Could not send password reset email. Please try again or contact support.', 'danger')

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"Error processing password reset request for {email}: {e}", exc_info=True)
                    flash('An unexpected error occurred. Please try again.', 'danger')
        # else: Email not found

        if not processed:
             # If no user was found, flash the generic message for security
             flash('If an account with that email exists and is confirmed, password reset instructions have been sent.', 'info')
             app.logger.info(f"Password reset requested for non-existent email: {email}")

        # Always redirect after POST to prevent resubmission
        return redirect(url_for('auth.login'))

    # Show form for GET request
    return render_template('reset_password_request.html')


@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('interview_page'))

    # Verify itsdangerous token (expiry, signature)
    user_id = verify_password_reset_itsdangerous_token(token)
    if user_id is None:
         flash('The password reset link is invalid or has expired.', 'danger')
         return redirect(url_for('auth.login'))

    # Check if the token hash exists in the DB
    reset_record = PasswordReset.query.filter_by(user_id=user_id)\
                                      .order_by(PasswordReset.created_at.desc())\
                                      .first()

    if not reset_record or not reset_record.check_token(token):
        flash('The password reset link is invalid or has already been used.', 'danger')
        app.logger.warning(f"Invalid/used password reset token check in DB for user_id {user_id}. Token: {token[:10]}...")
        return redirect(url_for('auth.login'))

    # Token is valid and matches DB record
    user = User.query.get(user_id)
    if not user:
         flash('User associated with this link not found.', 'danger')
         if reset_record: # Clean up orphan record
             db.session.delete(reset_record)
             db.session.commit()
         return redirect(url_for('auth.login'))

    # Handle password update form
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        error = None

        if not password or not confirm_password:
            error = 'Both password fields are required.'
        elif len(password) < 8:
             error = 'Password must be at least 8 characters long.'
        elif password != confirm_password:
            error = 'Passwords do not match.'

        if error is None:
            try:
                user.set_password(password) # Hashes the password
                user.failed_attempts = 0
                user.is_locked = False # Unlock account
                db.session.delete(reset_record) # Delete the used token record
                db.session.commit()

                flash('Your password has been reset successfully. Please log in.', 'success')
                app.logger.info(f"Password reset completed successfully for user {user.email}")
                return redirect(url_for('auth.login'))
            except Exception as e:
                 db.session.rollback()
                 app.logger.error(f"Error setting new password or deleting reset record for {user.email}: {e}", exc_info=True)
                 flash('An error occurred while resetting the password. Please try again.', 'danger')
                 # Don't set 'error' here, flash is enough

        # If validation failed
        if error:
            flash(error, 'danger')

    # Show form for GET or if POST had errors
    return render_template('reset_password.html', token=token)


@auth_bp.route('/resend_confirmation', methods=['POST'])
def resend_confirmation_email():
    """Handles requests to resend the confirmation email."""
    email = request.form.get('email', '').lower().strip()
    if not email:
        flash('Email address is required.', 'danger')
        return redirect(url_for('auth.login')) # Or wherever the request originated

    user = User.query.filter_by(email=email).first()

    if not user:
        # Use a generic message for security - don't reveal if email exists
        flash('If an account with that email exists and requires confirmation, a new email has been sent.', 'info')
        app.logger.info(f"Resend confirmation requested for non-existent or already confirmed email: {email}")
        return redirect(url_for('auth.login'))

    if user.is_confirmed:
        flash('Your account is already confirmed. Please log in.', 'info')
        app.logger.info(f"Resend confirmation requested for already confirmed email: {email}")
        return redirect(url_for('auth.login'))

    # User exists and is not confirmed, proceed to resend
    try:
        # Generate a new token (this updates user.confirmation_sent_at)
        token = generate_confirmation_token(user)
        # Commit the change to confirmation_sent_at
        db.session.commit()
        app.logger.info(f"Generated new confirmation token for resend request: {email}")

        # Send the email
        confirm_url = url_for('auth.confirm_email', token=token, _external=True)
        html = render_template('email/confirm_email.html', confirm_url=confirm_url)
        subject = "Confirm Your Email Address (Resend)"

        if send_email(user.email, subject, html):
            flash('A new confirmation email has been sent. Please check your inbox.', 'success')
            app.logger.info(f"Resent confirmation email successfully to {email}")
        else:
            # Rollback the timestamp update if email sending fails
            db.session.rollback()
            app.logger.error(f"Failed to resend confirmation email to {email}. Timestamp update rolled back.")
            flash('Could not send confirmation email. Please try again later or contact support.', 'danger')

    except Exception as e:
        db.session.rollback() # Rollback any potential DB changes on error
        app.logger.error(f"Error during resend confirmation process for {email}: {e}", exc_info=True)
        flash('An unexpected error occurred while resending the confirmation email.', 'danger')

    return redirect(url_for('auth.login')) # Redirect back to login page
