from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from models import db, User, Product, Cart, CartItem, Feedback, Order, OrderItem, Category

# Initialize Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Để sử dụng flash message

# Configure SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)  # Khởi tạo SQLAlchemy với app

# Define models (already defined in your case)
with app.app_context():
    db.create_all()
    
    # Kiểm tra và tạo tài khoản admin nếu chưa tồn tại
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', email='admin@example.com', address='Admin Address')
        admin.set_password('18022002')  
        admin.is_admin = True
        db.session.add(admin)
        db.session.commit()
        print('Admin account created')

def add_default_categories():
    categories = ['truyện việt nam', 'truyện nước ngoài', 'truyện khác']
    for category_name in categories:
        if not Category.query.filter_by(name=category_name).first():
            new_category = Category(name=category_name)
            db.session.add(new_category)
    db.session.commit()

@app.context_processor
def inject_user():
    current_user = None
    if 'user_id' in session:
        current_user = User.query.get(session['user_id'])
    return dict(current_user=current_user)

@app.route('/intro')
def intro():
    return render_template('intro.html')

@app.route('/index')
def index():
    current_user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            current_user = user
    
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category', type=int)
    per_page = 8

    if category_id:
        new_products = Product.query.filter_by(category_id=category_id).order_by(Product.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    else:
        new_products = Product.query.order_by(Product.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    categories = Category.query.all()

    return render_template('index.html', current_user=current_user, new_products=new_products, categories=categories, selected_category=category_id)


@app.route('/')
def show_login():
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['user_id'] = user.id  # Lưu user_id vào session
            if user.is_admin:
                return redirect(url_for('admin_products'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Tên đăng nhập hoặc mật khẩu không đúng.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)  # Xóa user_id khỏi session khi logout
    flash('Bạn đã đăng xuất thành công.', 'success')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Kiểm tra xem username đã tồn tại chưa
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Tên người dùng đã tồn tại. Vui lòng chọn tên khác.', 'danger')
            return redirect(url_for('register'))
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return redirect(url_for('register'))

        # Nếu không tồn tại, tiếp tục quá trình đăng ký
        new_user = User(username=username, email=email, password_hash=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        flash('Đăng ký thành công!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


# Admin routes for managing products
@app.route('/admin/products')
def admin_products():
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để truy cập trang này.', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        flash('Bạn không có quyền truy cập trang này.', 'danger')
        return redirect(url_for('index'))

    products = Product.query.all()
    return render_template('admin_products.html', products=products)


@app.route('/admin/products/add', methods=['GET', 'POST'])
def admin_add_product():
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để truy cập trang này.', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        flash('Bạn không có quyền truy cập trang này.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')
        image_url = request.form.get('image_url')
        author = request.form.get('author')  # Nhận tác giả từ form
        category_id = request.form.get('category')  # Nhận danh mục từ form

        new_product = Product(
            name=name,
            description=description,
            price=price,
            image_url=image_url,
            author=author,
            category_id=category_id  # Lưu category_id
        )
        db.session.add(new_product)
        db.session.commit()
        flash('Sản phẩm mới đã được thêm.', 'success')
        return redirect(url_for('admin_products'))

    # Lấy danh sách danh mục để truyền vào template
    categories = Category.query.all()
    return render_template('admin_add_product.html', categories=categories)


@app.route('/admin/products/edit/<int:product_id>', methods=['GET', 'POST'])
def admin_edit_product(product_id):
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để truy cập trang này.', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        flash('Bạn không có quyền truy cập trang này.', 'danger')
        return redirect(url_for('index'))

    product = Product.query.get_or_404(product_id)

    # Lấy danh sách danh mục từ cơ sở dữ liệu
    categories = Category.query.all()

    if request.method == 'POST':
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.price = request.form.get('price')
        product.image_url = request.form.get('image_url')
        product.author = request.form.get('author')
        product.category_id = request.form['category']  # Sửa tên trường thành 'category'

        db.session.commit()
        flash('Sản phẩm đã được cập nhật.', 'success')
        return redirect(url_for('admin_products'))

    return render_template('admin_edit_product.html', product=product, categories=categories)

@app.route('/admin/products/delete/<int:product_id>', methods=['POST'])
def admin_delete_product(product_id):
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để truy cập trang này.', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        flash('Bạn không có quyền truy cập trang này.', 'danger')
        return redirect(url_for('index'))

    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash('Sản phẩm đã bị xóa.', 'success')
    return redirect(url_for('admin_products'))

# Admin routes for managing users
@app.route('/admin/users', methods=['GET'])
def admin_users():
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để truy cập trang này.', 'danger')
        return redirect(url_for('login'))

    user = db.session.get(User, session['user_id'])
    if not user or not user.is_admin:
        flash('Bạn không có quyền truy cập trang này.', 'danger')
        return redirect(url_for('index'))

    users = User.query.filter(User.username != 'admin').all()  # Loại trừ người dùng admin
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/add', methods=['GET', 'POST'])
def admin_add_user():
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để truy cập trang này.', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        flash('Bạn không có quyền truy cập trang này.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        address = request.form.get('address')
        is_admin = request.form.get('is_admin') == 'on'
        balance = float(request.form.get('balance', 0))  # Nhận giá trị số dư tiền từ form

        if password != confirm_password:
            flash('Xác nhận mật khẩu không khớp.', 'danger')
        else:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('Email đã tồn tại. Vui lòng chọn email khác.', 'danger')
            else:
                new_user = User(username=username, email=email, address=address, is_admin=is_admin, balance=balance)
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.commit()
                flash('Người dùng mới đã được thêm.', 'success')
                return redirect(url_for('admin_users'))

    return render_template('admin_add_user.html')


@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
def admin_edit_user(user_id):
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để truy cập trang này.', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        flash('Bạn không có quyền truy cập trang này.', 'danger')
        return redirect(url_for('index'))

    # Lấy thông tin người dùng để sửa
    edit_user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        address = request.form.get('address')
        is_admin = request.form.get('is_admin') == 'on'
        balance = float(request.form.get('balance', 0))  # Nhận giá trị số dư tiền từ form

        # Kiểm tra xem email đã tồn tại chưa
        existing_user = User.query.filter(User.email == email, User.id != user_id).first()
        if existing_user:
            flash('Email đã tồn tại. Vui lòng chọn email khác.', 'danger')
        else:
            edit_user.username = username
            edit_user.email = email
            edit_user.address = address
            edit_user.is_admin = is_admin
            edit_user.balance = balance  # Cập nhật số dư tiền
            
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            if password and password == confirm_password:
                edit_user.set_password(password)
            
            db.session.commit()
            flash('Thông tin người dùng đã được cập nhật.', 'success')
            return redirect(url_for('admin_users'))

    return render_template('admin_edit_user.html', user=edit_user)  # Truyền thông tin người dùng cho template


@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
def admin_delete_user(user_id):
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để truy cập trang này.', 'danger')
        return redirect(url_for('login'))

    user = db.session.get(User, session['user_id'])
    if not user or not user.is_admin:
        flash('Bạn không có quyền truy cập trang này.', 'danger')
        return redirect(url_for('index'))

    user_to_delete = db.session.get(User, user_id)

    # Xử lý việc xóa các cart liên quan
    carts_to_delete = Cart.query.filter_by(user_id=user_to_delete.id).all()
    for cart in carts_to_delete:
        db.session.delete(cart)

    # Xử lý việc xóa các phản hồi liên quan
    feedbacks_to_delete = Feedback.query.filter_by(user_id=user_to_delete.id).all()
    for feedback in feedbacks_to_delete:
        db.session.delete(feedback)

    db.session.delete(user_to_delete)
    db.session.commit()
    flash('Người dùng đã bị xóa.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để truy cập trang này.', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        flash('Người dùng không tồn tại.', 'danger')
        return redirect(url_for('index'))


    orders = Order.query.filter_by(user_id = user.id).all()
    return render_template('profile.html', user=user, orders=orders)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product_detail.html', product=product)

@app.route('/buy/<int:product_id>', methods=['POST'])
def buy_product(product_id):
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để thực hiện mua hàng.', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    product = Product.query.get(product_id)

    if not product:
        flash('Không tìm thấy sản phẩm để mua.', 'danger')
        return redirect(url_for('index'))

    # Lấy giỏ hàng hiện tại của người dùng
    cart = Cart.query.filter_by(user_id=user.id).first()

    # Kiểm tra xem có giỏ hàng hay không
    if cart:
        # Lấy CartItem của sản phẩm từ giỏ hàng
        cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
        if cart_item:
            quantity = cart_item.quantity
        else:
            quantity = 1  # Nếu không có trong giỏ hàng, mặc định là 1
    else:
        quantity = 1  # Nếu không có giỏ hàng, mặc định là 1

    total_price = product.price * quantity

    # Kiểm tra xem người dùng có đủ tiền để mua không
    if user.balance < total_price:
        flash('Bạn không đủ tiền để thực hiện giao dịch này.', 'danger')
        return redirect(url_for('cart'))

    # Tạo đơn hàng mới
    new_order = Order(user_id=user.id, total_price=total_price)
    order_item = OrderItem(product_id=product.id, quantity=quantity, unit_price=product.price)
    new_order.items.append(order_item)

    try:
        # Giảm số tiền của người dùng
        user.balance -= total_price
        db.session.commit()  # Cập nhật số dư của người dùng

        db.session.add(new_order)
        db.session.commit()

        # Nếu sản phẩm có trong giỏ hàng, xóa khỏi giỏ hàng
        if cart_item:
            db.session.delete(cart_item)
            db.session.commit()

        flash('Đã đặt hàng thành công!', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        flash('Đã xảy ra lỗi khi đặt hàng. Vui lòng thử lại sau.', 'danger')
        app.logger.error(f"Error while placing order: {str(e)}")
        return redirect(url_for('index'))

    
@app.route('/admin/orders')
def admin_orders():
    if 'user_id' not in session or not User.query.get(session['user_id']).is_admin:
        flash('Bạn cần đăng nhập với tài khoản admin để truy cập.', 'danger')
        return redirect(url_for('login'))

    orders = Order.query.all()  # Thay thế bằng câu truy vấn thực tế để lấy danh sách đơn hàng

    return render_template('admin_orders.html', orders=orders)

@app.route('/admin/orders/approve/<int:order_id>', methods=['POST'])
def approve_order(order_id):
    if 'user_id' not in session or not User.query.get(session['user_id']).is_admin:
        flash('Bạn cần đăng nhập với tài khoản admin để truy cập.', 'danger')
        return redirect(url_for('login'))

    order = Order.query.get(order_id)
    if order:
        order.status = 'đang chờ hàng vận chuyển'
        db.session.commit()
        flash('Đơn hàng đã được duyệt.', 'success')                 
    return redirect(url_for('admin_orders'))

@app.route('/admin/orders/reject/<int:order_id>', methods=['POST'])
def reject_order(order_id):
    if 'user_id' not in session or not User.query.get(session['user_id']).is_admin:
        flash('Bạn cần đăng nhập với tài khoản admin để truy cập.', 'danger')
        return redirect(url_for('login'))

    order = Order.query.get(order_id)
    if order:
        # Hoàn lại số tiền cho người dùng
        user = User.query.get(order.user_id)
        user.balance += order.total_price  # Hoàn lại số tiền
        db.session.commit()  # Lưu thay đổi

        order.status = 'đơn đã bị hủy'  # Cập nhật trạng thái đơn hàng
        db.session.commit()  # Lưu thay đổi
        flash('Đơn hàng đã bị hủy và số tiền đã được hoàn lại cho người dùng.', 'success')
    else:
        flash('Không tìm thấy đơn hàng để hủy.', 'danger')

    return redirect(url_for('admin_orders'))



@app.route('/cart')
def view_cart():
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để truy cập trang này.', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        flash('Người dùng không tồn tại.', 'danger')
        return redirect(url_for('index'))

    # Lấy giỏ hàng hiện tại của người dùng
    cart = Cart.query.filter_by(user_id=user.id).first()
    # if not cart:
    #     flash('Giỏ hàng của bạn đang trống.', 'info')
    #     return redirect(url_for('cart.html'))


    return render_template('cart.html', cart=cart)

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để truy cập trang này.', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        flash('Người dùng không tồn tại.', 'danger')
        return redirect(url_for('index'))

    product = Product.query.get_or_404(product_id)

    # Lấy giỏ hàng hiện tại của người dùng
    cart = Cart.query.filter_by(user_id=user.id).first()
    if not cart:
        cart = Cart(user_id=user.id)
        db.session.add(cart)
        db.session.commit()

    # Kiểm tra xem sản phẩm đã có trong giỏ hàng chưa
    cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = CartItem(cart_id=cart.id, product_id=product.id)
        db.session.add(cart_item)

    db.session.commit()
    flash('Sản phẩm đã được thêm vào giỏ hàng.', 'success')
    return redirect(url_for('view_cart'))

@app.route('/remove_from_cart/<int:item_id>', methods=['POST'])
def remove_from_cart(item_id):
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để truy cập trang này.', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        flash('Người dùng không tồn tại.', 'danger')
        return redirect(url_for('index'))

    cart_item = CartItem.query.get_or_404(item_id)
    db.session.delete(cart_item)
    db.session.commit()
    flash('Sản phẩm đã được xóa khỏi giỏ hàng.', 'success')
    return redirect(url_for('view_cart'))

@app.route('/update_cart/<int:item_id>', methods=['POST'])
def update_cart(item_id):
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để truy cập trang này.', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        flash('Người dùng không tồn tại.', 'danger')
        return redirect(url_for('index'))

    cart = Cart.query.filter_by(user_id=user.id).first()
    if not cart:
        flash('Giỏ hàng của bạn đang trống.', 'info')
        return redirect(url_for('index'))

    cart_item = CartItem.query.filter_by(id=item_id, cart_id=cart.id).first()
    if not cart_item:
        flash('Sản phẩm không có trong giỏ hàng của bạn.', 'danger')
        return redirect(url_for('view_cart'))

    quantity = int(request.form.get('quantity', 1))  # Mặc định là 1 nếu không có giá trị
    if quantity <= 0:
        flash('Số lượng sản phẩm phải lớn hơn 0.', 'danger')
        return redirect(url_for('view_cart'))
    
    if quantity > 100000:
        flash('Số lượng không thể lớn hơn 100.000.', 'danger')
        return redirect(url_for('view_cart'))

    cart_item.quantity = quantity
    db.session.commit()

    flash('Giỏ hàng của bạn đã được cập nhật.', 'success')
    return redirect(url_for('view_cart'))


@app.route('/search')
def search():
    query = request.args.get('query', '')
    if query:
        # Tìm các sản phẩm có tên chứa từ khóa tìm kiếm
        products = Product.query.filter(Product.name.ilike(f'%{query}%')).all()
    else:
        products = []
    return render_template('search_results.html', products=products, query=query)

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để gửi phản hồi.', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        flash('Người dùng không tồn tại.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            new_feedback = Feedback(user_id=user.id, content=content)
            db.session.add(new_feedback)
            db.session.commit()
            flash('Phản hồi của bạn đã được gửi.', 'success')
            return redirect(url_for('feedback'))
        else:
            flash('Nội dung phản hồi không được để trống.', 'danger')

    # Hiển thị các phản hồi của người dùng
    feedbacks = Feedback.query.filter_by(user_id=user.id).all()
    return render_template('feedback.html', feedbacks=feedbacks)

@app.route('/delete_feedback/<int:feedback_id>', methods=['POST'])
def delete_feedback(feedback_id):
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để thực hiện hành động này.', 'danger')
        return redirect(url_for('login'))

    feedback = Feedback.query.get(feedback_id)
    if feedback and feedback.user_id == session['user_id']:
        db.session.delete(feedback)
        db.session.commit()
        flash('Phản hồi đã được xóa thành công.', 'success')
    else:
        flash('Không tìm thấy phản hồi hoặc bạn không có quyền xóa.', 'danger')

    return redirect(url_for('feedback'))


@app.route('/admin/feedback')
def admin_feedback():
    if 'user_id' not in session or not User.query.get(session['user_id']).is_admin:
        flash('Bạn cần đăng nhập với tài khoản admin để truy cập.', 'danger')
        return redirect(url_for('login'))

    feedbacks = Feedback.query.all()
    return render_template('admin_feedback.html', feedbacks=feedbacks)


@app.route('/admin/feedback/respond/<int:feedback_id>', methods=['POST'])
def admin_respond_feedback(feedback_id):
    if 'user_id' not in session or not User.query.get(session['user_id']).is_admin:
        flash('Bạn cần đăng nhập với tài khoản admin để truy cập.', 'danger')
        return redirect(url_for('login'))

    feedback = Feedback.query.get(feedback_id)
    if feedback:
        feedback.response = request.form.get('response')
        db.session.commit()
        flash('Phản hồi của admin đã được gửi.', 'success')
    else:
        flash('Phản hồi không tồn tại.', 'danger')

    return redirect(url_for('admin_feedback'))

@app.route('/admin/feedback/delete/<int:feedback_id>', methods=['POST'])
def admin_delete_feedback(feedback_id):
    if 'user_id' not in session or not User.query.get(session['user_id']).is_admin:
        flash('Bạn cần đăng nhập với tài khoản admin để truy cập.', 'danger')
        return redirect(url_for('login'))

    feedback = Feedback.query.get_or_404(feedback_id)
    db.session.delete(feedback)
    db.session.commit()
    flash('Phản hồi đã bị xóa.', 'success')
    return redirect(url_for('admin_feedback'))

@app.route('/checkout', methods=['POST'])
def checkout():
    # Logic xử lý thanh toán
    return redirect(url_for('some_view'))

if __name__ == '__main__':
    with app.app_context():
        add_default_categories()
    app.run(host='0.0.0.0', port=1234, debug=True)
