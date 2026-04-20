from models import db, User, Availability, Shift
from sqlalchemy import func
import random

def generate_roster(target_date, target_slot, group_filter=None):
    """
    智能排班算法：
    1. 筛选该时间段有空的人
    2. 排除今天已经上过太多班的人（限制单日时长）
    3. 按累积值班次数排序，取最少的人（公平原则）
    """
    # 1. 找出该时间段有空的用户
    query = db.session.query(User).join(Availability).filter(
        Availability.date == target_date,
        Availability.slot == target_slot
    )
    
    if group_filter:
        query = query.filter(User.group == group_filter)
        
    available_users = query.all()
    
    if not available_users:
        return None

    # 2. 限制单日最高时长 (例如：一天最多排 3 个时段)
    MAX_DAILY_SLOTS = 3
    final_candidates = []
    
    for user in available_users:
        daily_count = db.session.query(Shift).filter(
            Shift.user_id == user.id,
            Shift.date == target_date,
            Shift.status == 'confirmed'
        ).count()
        
        if daily_count < MAX_DAILY_SLOTS:
            final_candidates.append(user)
            
    if not final_candidates:
        return None # 该天大家都排满了

    # 3. 平均分配逻辑：按累积值班次数排序
    user_counts = []
    for user in final_candidates:
        count = db.session.query(Shift).filter(
            Shift.user_id == user.id, 
            Shift.status == 'confirmed'
        ).count()
        user_counts.append((user, count))
    
    # 排序：次数少的排前面
    user_counts.sort(key=lambda x: x[1])
    
    # 选取次数最少的那位 (如果有多个并列最少，随机选一个增加随机性)
    min_count = user_counts[0][1]
    candidates_with_min = [u for u, c in user_counts if c == min_count]
    
    selected_user = random.choice(candidates_with_min)
    
    # 4. 写入数据库
    new_shift = Shift(user_id=selected_user.id, date=target_date, slot=target_slot)
    db.session.add(new_shift)
    db.session.commit()
    
    return selected_user