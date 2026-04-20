import os
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Availability, Shift, SwapRequest
from scheduler import generate_roster
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'dev-key'

# 适配 Render 的 PostgreSQL 环境变量
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- 初始化数据库 ---
def init_db():
    with app.app_context():
        db.create_all()
        # 创建默认管理员
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', name='系统管理员', group='Admin', 
                         password=generate_password_hash('admin123'), is_admin=True)
            db.session.add(admin)
            db.session.commit()

# --- 认证路由 ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('账号或密码错误')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- 员工功能 ---
@app.route('/')
@login_required
def dashboard():
    my_shifts_count = Shift.query.filter_by(user_id=current_user.id, status='confirmed').count()
    my_received_requests = SwapRequest.query.filter_by(to_user_id=current_user.id, status='pending').all()
    my_sent_requests = SwapRequest.query.filter_by(from_user_id=current_user.id, status='pending').all()
    return render_template('dashboard.html', count=my_shifts_count, recv_reqs=my_received_requests, sent_reqs=my_sent_requests)

@app.route('/availability', methods=['GET', 'POST'])
@login_required
def set_availability():
    if request.method == 'POST':
        # 删除旧的，全量更新
        Availability.query.filter_by(user_id=current_user.id).delete()
        
        data = request.json 
        for item in data:
            date_obj = datetime.strptime(item['date'], '%Y-%m-%d').date()
            for slot in item['slots']:
                avail = Availability(user_id=current_user.id, date=date_obj, slot=slot)
                db.session.add(avail)
        db.session.commit()
        return jsonify({'success': True})
        
    # 生成未来 30 天日期
    dates = []
    for i in range(30):
        dates.append((datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d'))
    return render_template('availability.html', dates=dates)

@app.route('/schedule')
@login_required
def view_schedule():
    shifts = Shift.query.filter_by(user_id=current_user.id).order_by(Shift.date).all()
    return render_template('schedule_view.html', shifts=shifts, is_admin=current_user.is_admin)

# --- 换班逻辑 ---
@app.route('/swap_request/<int:shift_id>', methods=['POST'])
@login_required
def create_swap_request(shift_id):
    shift = Shift.query.get(shift_id)
    if shift.user_id != current_user.id: return "无权操作", 403
    
    target_user_id = request.form['target_user_id']
    exists = SwapRequest.query.filter_by(shift_id=shift_id, status='pending').first()
    if exists:
        flash('已有待处理的换班申请')
        return redirect(url_for('dashboard'))

    new_req = SwapRequest(from_user_id=current_user.id, to_user_id=target_user_id, shift_id=shift_id)
    db.session.add(new_req)
    db.session.commit()
    flash('换班申请已发送')
    return redirect(url_for('dashboard'))

@app.route('/swap_approve/<int:req_id>')
@login_required
def approve_swap(req_id):
    req = SwapRequest.query.get(req_id)
    if req.to_user_id != current_user.id: return redirect(url_for('dashboard'))
    
    shift = Shift.query.get(req.shift_id)
    shift.user_id = current_user.id 
    req.status = 'approved'
    db.session.commit()
    flash('换班成功')
    return redirect(url_for('dashboard'))

# --- 管理员功能 ---
@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    
    users = User.query.all()
    stats = []
    for u in users:
        cnt = Shift.query.filter_by(user_id=u.id, status='confirmed').count()
        stats.append({'id': u.id, 'name': u.name, 'username': u.username, 'group': u.group, 'count': cnt})
    
    return render_template('admin.html', users=stats)

@app.route('/admin/import', methods=['POST'])
@login_required
def import_users():
    if not current_user.is_admin: return "Unauthorized", 403
    
    file = request.files['file']
    if not file: return redirect(url_for('admin_panel'))
        
    try:
        # 读取 Excel (支持 xls 和 xlsx)
        df = pd.read_excel(file)
        # 期望列: 姓名, 账号, 密码, 组别
        for _, row in df.iterrows():
            username = str(row['账号']).strip()
            name = str(row['姓名']).strip()
            password = str(row['密码']).strip()
            group = str(row.get('组别', 'Default')).strip()
            
            # 检查账号是否存在
            if not User.query.filter_by(username=username).first():
                new_user = User(
                    username=username, 
                    name=name, 
                    password=generate_password_hash(password),
                    group=group,
                    is_admin=False
                )
                db.session.add(new_user)
        db.session.commit()
        flash('导入成功！')
    except Exception as e:
        db.session.rollback()
        flash(f'导入失败: {str(e)}')
        
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete/<int:user_id>')
@login_required
def delete_user(user_id):
    if not current_user.is_admin: return "Unauthorized", 403
    user = User.query.get(user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
        flash('用户已删除')
    return redirect(url_for('admin_panel'))

@app.route('/admin/generate', methods=['POST'])
@login_required
def admin_generate():
    if not current_user.is_admin: return "Unauthorized", 403
    
    target_date_str = request.form['date']
    target_slot = int(request.form['slot'])
    group = request.form.get('group')
    
    target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    
    # 检查是否已存在
    existing = Shift.query.filter_by(date=target_date, slot=target_slot).first()
    if existing:
        flash('该时间段已有排班')
        return redirect(url_for('admin_panel'))

    user = generate_roster(target_date, target_slot, group)
    if user:
        flash(f'排班成功: {user.name} (累积: {user.shifts|length}次)')
    else:
        flash('无人可用，请检查空闲时间设置或单日限制')
        
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)