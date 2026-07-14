from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, ValidationError

from app.security import password_policy_errors


class LoginForm(FlaskForm):
    username_or_email = StringField("Tên đăng nhập hoặc email", validators=[DataRequired(), Length(max=255)])
    password = PasswordField("Mật khẩu", validators=[DataRequired()])
    remember = BooleanField("Ghi nhớ đăng nhập")
    submit = SubmitField("Đăng nhập")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Mật khẩu hiện tại", validators=[DataRequired()])
    new_password = PasswordField("Mật khẩu mới", validators=[DataRequired(), Length(max=128)])
    confirm_password = PasswordField(
        "Xác nhận mật khẩu mới",
        validators=[DataRequired(), EqualTo("new_password", message="Mật khẩu xác nhận không khớp.")],
    )
    submit = SubmitField("Đổi mật khẩu")

    def validate_new_password(self, field):
        errors = password_policy_errors(field.data)
        if errors:
            raise ValidationError(" ".join(errors))
