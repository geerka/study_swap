from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from models import db, User, Category, StudyMaterial, Review, Order, OrderItem, University, Tag, cart_items
import os
import uuid
from datetime import datetime

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///studyswap.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
ALLOWED_EXTENSIONS = {'pdf', 'zip', 'pptx', 'docx', 'txt', 'png', 'jpg', 'jpeg'}

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Create database tables
with app.app_context():
    db.create_all()
    
    # Add sample categories if empty
    if Category.query.count() == 0:
        categories = [
            Category(name='Programming', slug='programming', icon='bi-code-slash'),
            Category(name='Mathematics', slug='mathematics', icon='bi-calculator'),
            Category(name='Science', slug='science', icon='bi-journal-bookmark'),
            Category(name='Networking', slug='networking', icon='bi-diagram-3'),
            Category(name='Business', slug='business', icon='bi-briefcase'),
            Category(name='Writing', slug='writing', icon='bi-pencil'),
        ]
        db.session.add_all(categories)
        db.session.commit()

# Create uploads folder if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


# ==================== HOME & BROWSE ====================

@app.route("/")
def home():
    categories = Category.query.all()
    featured_materials = StudyMaterial.query.filter_by(is_featured=True, is_active=True).limit(6).all()
    best_sellers = StudyMaterial.query.filter_by(is_best_seller=True, is_active=True).limit(4).all()
    recent_materials = StudyMaterial.query.filter_by(is_active=True).order_by(StudyMaterial.created_at.desc()).limit(8).all()
    
    # Stats for hero section
    total_materials = StudyMaterial.query.filter_by(is_active=True).count()
    total_sellers = User.query.filter_by(is_seller=True).count()
    
    return render_template("index.html", 
                         categories=categories, 
                         featured_materials=featured_materials,
                         best_sellers=best_sellers,
                         recent_materials=recent_materials,
                         total_materials=total_materials,
                         total_sellers=total_sellers)


@app.route("/browse")
def browse():
    page = request.args.get('page', 1, type=int)
    per_page = 12
    
    # Get filter parameters
    category_slug = request.args.get('category')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    file_type = request.args.get('file_type')
    sort_by = request.args.get('sort', 'newest')
    search_query = request.args.get('q', '')
    
    # Base query
    query = StudyMaterial.query.filter_by(is_active=True)
    
    # Apply filters
    if category_slug:
        cat = Category.query.filter_by(slug=category_slug).first()
        if cat:
            query = query.filter_by(category_id=cat.id)
    
    if min_price is not None:
        query = query.filter(StudyMaterial.price >= min_price)
    
    if max_price is not None:
        query = query.filter(StudyMaterial.price <= max_price)
    
    if file_type:
        query = query.filter_by(file_type=file_type)
    
    if search_query:
        query = query.filter(
            db.or_(
                StudyMaterial.title.ilike(f'%{search_query}%'),
                StudyMaterial.description.ilike(f'%{search_query}%'),
                StudyMaterial.course_code.ilike(f'%{search_query}%'),
                StudyMaterial.subject.ilike(f'%{search_query}%')
            )
        )
    
    # Apply sorting
    if sort_by == 'newest':
        query = query.order_by(StudyMaterial.created_at.desc())
    elif sort_by == 'oldest':
        query = query.order_by(StudyMaterial.created_at.asc())
    elif sort_by == 'price_low':
        query = query.order_by(StudyMaterial.price.asc())
    elif sort_by == 'price_high':
        query = query.order_by(StudyMaterial.price.desc())
    elif sort_by == 'popular':
        query = query.order_by(StudyMaterial.downloads.desc())
    elif sort_by == 'rating':
        query = query.order_by(StudyMaterial.rating.desc())
    
    # Paginate
    materials = query.paginate(page=page, per_page=per_page)
    categories = Category.query.all()
    
    return render_template("browse.html", 
                         materials=materials, 
                         categories=categories,
                         current_category=category_slug,
                         search_query=search_query,
                         sort_by=sort_by)


@app.route("/search")
def search():
    q = request.args.get('q', '')
    if not q:
        return redirect(url_for('browse'))
    return redirect(url_for('browse', q=q))


# ==================== MATERIAL DETAIL ====================

@app.route("/material/<int:id>")
def material_detail(id):
    material = StudyMaterial.query.get_or_404(id)
    material.views += 1
    db.session.commit()
    
    # Get related materials
    related = StudyMaterial.query.filter(
        StudyMaterial.category_id == material.category_id,
        StudyMaterial.id != material.id,
        StudyMaterial.is_active == True
    ).limit(4).all()
    
    # Check if user has purchased this material
    has_purchased = False
    if current_user.is_authenticated:
        order_item = OrderItem.query.join(Order).filter(
            Order.buyer_id == current_user.id,
            OrderItem.material_id == material.id,
            Order.status == 'completed'
        ).first()
        has_purchased = order_item is not None
    
    return render_template("material_detail.html", 
                         material=material, 
                         related=related,
                         has_purchased=has_purchased)


@app.route("/category/<slug>")
def category(slug):
    cat = Category.query.filter_by(slug=slug).first_or_404()
    page = request.args.get('page', 1, type=int)
    materials = cat.materials.filter_by(is_active=True).paginate(page=page, per_page=12)
    return render_template("category.html", category=cat, materials=materials)


# ==================== AUTHENTICATION ====================

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not all([username, email, password, confirm_password]):
            flash('Všetky polia sú povinné.', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Heslá sa nezhodujú.', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Používateľské meno už existuje.', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email už je registrovaný.', 'error')
            return render_template('register.html')
        
        # Create user
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registrácia úspešná! Teraz sa môžete prihlásiť.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            next_page = request.args.get('next')
            flash('Prihlásenie úspešné!', 'success')
            return redirect(next_page or url_for('home'))
        else:
            flash('Nesprávny email alebo heslo.', 'error')
    
    return render_template('login.html')


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash('Boli ste odhlásení.', 'success')
    return redirect(url_for('home'))


# ==================== USER PROFILE ====================

@app.route("/profile")
@login_required
def profile():
    user_materials = current_user.materials.order_by(StudyMaterial.created_at.desc()).all()
    user_orders = current_user.orders.order_by(Order.created_at.desc()).all()
    return render_template('profile.html', materials=user_materials, orders=user_orders)


@app.route("/profile/edit", methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name')
        current_user.last_name = request.form.get('last_name')
        current_user.university = request.form.get('university')
        current_user.bio = request.form.get('bio')
        
        db.session.commit()
        flash('Profil bol aktualizovaný.', 'success')
        return redirect(url_for('profile'))
    
    return render_template('edit_profile.html')


@app.route("/seller/<int:id>")
def seller_profile(id):
    seller = User.query.get_or_404(id)
    materials = seller.materials.filter_by(is_active=True).all()
    return render_template('seller_profile.html', seller=seller, materials=materials)


# ==================== SELL MATERIALS ====================

@app.route("/sell", methods=['GET', 'POST'])
@login_required
def sell():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        price = request.form.get('price', type=float)
        category_id = request.form.get('category_id', type=int)
        course_code = request.form.get('course_code')
        university = request.form.get('university')
        subject = request.form.get('subject')
        
        # Handle file upload
        if 'file' not in request.files:
            flash('Súbor je povinný.', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('Nebol vybraný žiadny súbor.', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Generate unique filename
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Get file size
            file_size = os.path.getsize(filepath)
            
            # Handle preview image
            preview_filename = None
            if 'preview' in request.files:
                preview = request.files['preview']
                if preview.filename and allowed_file(preview.filename):
                    preview_ext = preview.filename.rsplit('.', 1)[1].lower()
                    preview_filename = f"preview_{uuid.uuid4().hex}.{preview_ext}"
                    preview.save(os.path.join(app.config['UPLOAD_FOLDER'], preview_filename))
            
            # Create material
            material = StudyMaterial(
                title=title,
                description=description,
                price=price,
                file_path=filename,
                file_type=ext,
                file_size=file_size,
                preview_image=preview_filename,
                category_id=category_id,
                course_code=course_code,
                university=university,
                subject=subject,
                seller_id=current_user.id
            )
            
            # Mark user as seller
            if not current_user.is_seller:
                current_user.is_seller = True
            
            db.session.add(material)
            db.session.commit()
            
            flash('Materiál bol úspešne pridaný!', 'success')
            return redirect(url_for('material_detail', id=material.id))
        else:
            flash('Nepovolený typ súboru.', 'error')
    
    categories = Category.query.all()
    return render_template('sell.html', categories=categories)


@app.route("/material/<int:id>/edit", methods=['GET', 'POST'])
@login_required
def edit_material(id):
    material = StudyMaterial.query.get_or_404(id)
    
    if material.seller_id != current_user.id and not current_user.is_admin:
        flash('Nemáte oprávnenie upraviť tento materiál.', 'error')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        material.title = request.form.get('title')
        material.description = request.form.get('description')
        material.price = request.form.get('price', type=float)
        material.category_id = request.form.get('category_id', type=int)
        material.course_code = request.form.get('course_code')
        material.university = request.form.get('university')
        material.subject = request.form.get('subject')
        
        db.session.commit()
        flash('Materiál bol aktualizovaný.', 'success')
        return redirect(url_for('material_detail', id=material.id))
    
    categories = Category.query.all()
    return render_template('edit_material.html', material=material, categories=categories)


@app.route("/material/<int:id>/delete", methods=['POST'])
@login_required
def delete_material(id):
    material = StudyMaterial.query.get_or_404(id)
    
    if material.seller_id != current_user.id and not current_user.is_admin:
        flash('Nemáte oprávnenie vymazať tento materiál.', 'error')
        return redirect(url_for('home'))
    
    material.is_active = False
    db.session.commit()
    flash('Materiál bol vymazaný.', 'success')
    return redirect(url_for('profile'))


# ==================== CART ====================

@app.route("/cart")
@login_required
def cart():
    cart_total = sum(item.price for item in current_user.cart)
    return render_template('cart.html', cart_items=current_user.cart, cart_total=cart_total)


@app.route("/cart/add/<int:material_id>", methods=['POST'])
@login_required
def add_to_cart(material_id):
    material = StudyMaterial.query.get_or_404(material_id)
    
    if material.seller_id == current_user.id:
        flash('Nemôžete kúpiť vlastný materiál.', 'error')
        return redirect(url_for('material_detail', id=material_id))
    
    if material in current_user.cart:
        flash('Materiál je už v košíku.', 'info')
    else:
        current_user.cart.append(material)
        db.session.commit()
        flash('Pridané do košíka!', 'success')
    
    return redirect(request.referrer or url_for('cart'))


@app.route("/cart/remove/<int:material_id>", methods=['POST'])
@login_required
def remove_from_cart(material_id):
    material = StudyMaterial.query.get_or_404(material_id)
    
    if material in current_user.cart:
        current_user.cart.remove(material)
        db.session.commit()
        flash('Odstránené z košíka.', 'success')
    
    return redirect(url_for('cart'))


# ==================== CHECKOUT & ORDERS ====================

@app.route("/checkout", methods=['GET', 'POST'])
@login_required
def checkout():
    if not current_user.cart:
        flash('Váš košík je prázdny.', 'error')
        return redirect(url_for('browse'))
    
    if request.method == 'POST':
        # Create order
        order_number = f"SS-{uuid.uuid4().hex[:8].upper()}"
        total = sum(item.price for item in current_user.cart)
        
        order = Order(
            order_number=order_number,
            total_amount=total,
            status='completed',
            payment_method='card',
            buyer_id=current_user.id,
            completed_at=datetime.utcnow()
        )
        db.session.add(order)
        db.session.flush()
        
        # Create order items
        for material in current_user.cart:
            order_item = OrderItem(
                order_id=order.id,
                material_id=material.id,
                price=material.price
            )
            db.session.add(order_item)
            material.downloads += 1
            material.seller.total_earnings += material.price * 0.8
        
        # Clear cart
        current_user.cart = []
        db.session.commit()
        
        flash('Objednávka bola úspešná!', 'success')
        return redirect(url_for('order_detail', id=order.id))
    
    cart_total = sum(item.price for item in current_user.cart)
    return render_template('checkout.html', cart_items=current_user.cart, cart_total=cart_total)


@app.route("/order/<int:id>")
@login_required
def order_detail(id):
    order = Order.query.get_or_404(id)
    
    if order.buyer_id != current_user.id and not current_user.is_admin:
        flash('Nemáte oprávnenie zobraziť túto objednávku.', 'error')
        return redirect(url_for('home'))
    
    return render_template('order_detail.html', order=order)


@app.route("/orders")
@login_required
def orders():
    user_orders = current_user.orders.order_by(Order.created_at.desc()).all()
    return render_template('orders.html', orders=user_orders)


# ==================== DOWNLOADS ====================

@app.route("/download/<int:material_id>")
@login_required
def download_material(material_id):
    material = StudyMaterial.query.get_or_404(material_id)
    
    has_access = material.seller_id == current_user.id
    
    if not has_access:
        order_item = OrderItem.query.join(Order).filter(
            Order.buyer_id == current_user.id,
            OrderItem.material_id == material_id,
            Order.status == 'completed'
        ).first()
        has_access = order_item is not None
        
        if order_item:
            order_item.download_count += 1
            order_item.last_download = datetime.utcnow()
            db.session.commit()
    
    if not has_access:
        flash('Nemáte prístup k tomuto súboru.', 'error')
        return redirect(url_for('material_detail', id=material_id))
    
    return send_from_directory(
        app.config['UPLOAD_FOLDER'], 
        material.file_path,
        as_attachment=True,
        download_name=f"{material.title}.{material.file_type}"
    )


# ==================== REVIEWS ====================

@app.route("/material/<int:id>/review", methods=['POST'])
@login_required
def add_review(id):
    material = StudyMaterial.query.get_or_404(id)
    
    order_item = OrderItem.query.join(Order).filter(
        Order.buyer_id == current_user.id,
        OrderItem.material_id == id,
        Order.status == 'completed'
    ).first()
    
    if not order_item:
        flash('Môžete hodnotiť len zakúpené materiály.', 'error')
        return redirect(url_for('material_detail', id=id))
    
    existing_review = Review.query.filter_by(
        material_id=id,
        reviewer_id=current_user.id
    ).first()
    
    if existing_review:
        flash('Už ste tento materiál hodnotili.', 'error')
        return redirect(url_for('material_detail', id=id))
    
    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment')
    
    if not rating or rating < 1 or rating > 5:
        flash('Neplatné hodnotenie.', 'error')
        return redirect(url_for('material_detail', id=id))
    
    review = Review(
        rating=rating,
        comment=comment,
        material_id=id,
        reviewer_id=current_user.id,
        seller_id=material.seller_id
    )
    
    db.session.add(review)
    db.session.commit()
    
    material.update_rating()
    db.session.commit()
    
    flash('Hodnotenie bolo pridané.', 'success')
    return redirect(url_for('material_detail', id=id))


# ==================== FAVORITES ====================

@app.route("/favorites")
@login_required
def favorites():
    return render_template('favorites.html', favorites=current_user.favorite_materials)


@app.route("/favorites/toggle/<int:material_id>", methods=['POST'])
@login_required
def toggle_favorite(material_id):
    material = StudyMaterial.query.get_or_404(material_id)
    
    if material in current_user.favorite_materials:
        current_user.favorite_materials.remove(material)
        message = 'Odstránené z obľúbených.'
    else:
        current_user.favorite_materials.append(material)
        message = 'Pridané do obľúbených.'
    
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': message})
    
    flash(message, 'success')
    return redirect(request.referrer or url_for('home'))


# ==================== API ENDPOINTS ====================

@app.route("/api/cart/count")
def api_cart_count():
    if current_user.is_authenticated:
        return jsonify({'count': len(current_user.cart)})
    return jsonify({'count': 0})


@app.route("/api/search")
def api_search():
    q = request.args.get('q', '')
    if len(q) < 2:
        return jsonify([])
    
    materials = StudyMaterial.query.filter(
        StudyMaterial.is_active == True,
        db.or_(
            StudyMaterial.title.ilike(f'%{q}%'),
            StudyMaterial.course_code.ilike(f'%{q}%'),
            StudyMaterial.subject.ilike(f'%{q}%')
        )
    ).limit(10).all()
    
    results = [{
        'id': m.id,
        'title': m.title,
        'price': m.price,
        'category': m.category.name if m.category else None
    } for m in materials]
    
    return jsonify(results)


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500


# ==================== CONTEXT PROCESSORS ====================

@app.context_processor
def inject_globals():
    return dict(
        all_categories=Category.query.all(),
        cart_count=len(current_user.cart) if current_user.is_authenticated else 0
    )
