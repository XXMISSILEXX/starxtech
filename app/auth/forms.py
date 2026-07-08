from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length


class LoginForm(FlaskForm):
    username_or_email = StringField("Tên đăng nhập hoặc email", validators=[DataRequired(), Length(max=255)])
    password = PasswordField("Mật khẩu", validators=[DataRequired()])
    remember = BooleanField("Ghi nhớ đăng nhập")
    submit = SubmitField("Đăng nhập")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Mật khẩu hiện tại", validators=[DataRequired()])
    new_password = PasswordField("Mật khẩu mới", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField(
        "Xác nhận mật khẩu mới",
        validators=[DataRequired(), EqualTo("new_password", message="Mật khẩu xác nhận không khớp.")],
    )
    submit = SubmitField("Đổi mật khẩu")
