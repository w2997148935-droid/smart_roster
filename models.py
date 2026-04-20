from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False) # 账号
    name = db.Column(db.String(80), nullable=False) # 姓名
    password = db.Column(db.String(120), nullable=False)
    group = db.Column(db.String(50), nullable=False) # 组别
    is_admin = db.Column(db.Boolean, default=False)
    
    availabilities = db.relationship('Availability', backref='user', lazy=True)
    shifts = db.relationship('Shift', backref='user', lazy=True)

class Availability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    slot = db.Column(db.Integer, nullable=False) # 1-6 代表6个时间段

class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    slot = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='confirmed') # confirmed, leave, swapped

class SwapRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    shift_id = db.Column(db.Integer, db.ForeignKey('shift.id'), nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)