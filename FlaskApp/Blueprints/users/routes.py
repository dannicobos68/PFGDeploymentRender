from flask import render_template, request, jsonify, redirect, url_for, flash
from .forms import LoginForm, RegisterForm
from flask_login import login_user, current_user, logout_user
from sqlalchemy import or_
import datetime
from FlaskApp.database import User, db
from flask_login import login_required
from datetime import timedelta

def login():
    loginForm = LoginForm()
    print("Login")
    print(loginForm.validate_on_submit())
    if loginForm.validate_on_submit():
        username = loginForm.username.data
        password = loginForm.password.data
        user = User.query.filter(or_(User.email.like(username), User.username.like(username))).first()
        if user and user.check_password(password):
            login_user(user)
            print("Sesion iniciada con exito")
            return redirect(url_for('bp_main.index'))
        else:
            flash('Usuario o contraseña incorrectos', 'danger')    
    return render_template('login.html', form_login=loginForm)

def register():
    registerForm = RegisterForm()
    print("Register")
    print(registerForm.validate_on_submit())
    if registerForm.validate_on_submit():
        print("Register validate")
        username = registerForm.username.data
        email = registerForm.email.data
        # Check si el usuario ya existe
        user = User.query.filter(or_(User.email.like(email), User.username.like(username))).first()
        if user:
            flash('Usuario ya registrado', 'danger')
            return redirect(url_for('bp_users.register'))
        password = registerForm.password.data
        newUser = User(username=username, email=email)
        newUser.set_password(password)
        db.session.add(newUser)
        db.session.commit()
        flash('Usuario registrado con exito', 'success')
        return redirect(url_for('bp_users.login'))
    return render_template('register.html', form_register=registerForm)