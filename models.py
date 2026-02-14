from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Association table for cart items
cart_items = db.Table('cart_items',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('material_id', db.Integer, db.ForeignKey('study_material.id'), primary_key=True),
    db.Column('added_at', db.DateTime, default=datetime.utcnow)
)

# Association table for user favorites/wishlist
favorites = db.Table('favorites',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('material_id', db.Integer, db.ForeignKey('study_material.id'), primary_key=True)
)


class User(UserMixin, db.Model):
    """User model - can be buyer, seller, or both"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    
    # Profile info
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    university = db.Column(db.String(150))
    bio = db.Column(db.Text)
    profile_image = db.Column(db.String(255))
    
    # User type and status
    is_seller = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Seller stats
    total_earnings = db.Column(db.Float, default=0.0)
    seller_rating = db.Column(db.Float, default=0.0)
    
    # Relationships
    materials = db.relationship('StudyMaterial', backref='seller', lazy='dynamic')
    reviews_given = db.relationship('Review', foreign_keys='Review.reviewer_id', backref='reviewer', lazy='dynamic')
    reviews_received = db.relationship('Review', foreign_keys='Review.seller_id', backref='seller', lazy='dynamic')
    orders = db.relationship('Order', backref='buyer', lazy='dynamic')
    
    # Cart and favorites
    cart = db.relationship('StudyMaterial', secondary=cart_items, backref='in_carts')
    favorite_materials = db.relationship('StudyMaterial', secondary=favorites, backref='favorited_by')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Category(db.Model):
    """Categories for study materials"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))  # Bootstrap icon class
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    
    # Self-referential relationship for subcategories
    subcategories = db.relationship('Category', backref=db.backref('parent', remote_side=[id]))
    materials = db.relationship('StudyMaterial', backref='category', lazy='dynamic')
    
    def __repr__(self):
        return f'<Category {self.name}>'


class StudyMaterial(db.Model):
    """Study materials/products for sale"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    
    # Pricing
    price = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float)  # For showing discounts
    
    # File info
    file_path = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(20))  # pdf, zip, pptx, docx
    file_size = db.Column(db.Integer)  # in bytes
    preview_image = db.Column(db.String(255))
    
    # Categorization
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    course_code = db.Column(db.String(50))  # e.g., "CS101", "CCNA"
    university = db.Column(db.String(150))
    subject = db.Column(db.String(100))
    
    # Stats
    views = db.Column(db.Integer, default=0)
    downloads = db.Column(db.Integer, default=0)
    rating = db.Column(db.Float, default=0.0)
    rating_count = db.Column(db.Integer, default=0)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    is_best_seller = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    reviews = db.relationship('Review', backref='material', lazy='dynamic')
    order_items = db.relationship('OrderItem', backref='material', lazy='dynamic')
    
    def update_rating(self):
        """Recalculate average rating"""
        reviews = self.reviews.all()
        if reviews:
            self.rating = sum(r.rating for r in reviews) / len(reviews)
            self.rating_count = len(reviews)
        else:
            self.rating = 0.0
            self.rating_count = 0
    
    def __repr__(self):
        return f'<StudyMaterial {self.title}>'


class Review(db.Model):
    """Reviews for study materials"""
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    comment = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    material_id = db.Column(db.Integer, db.ForeignKey('study_material.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Helpful votes
    helpful_count = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<Review {self.rating} stars for material {self.material_id}>'


class Order(db.Model):
    """Purchase orders"""
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    
    # Order details
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, completed, refunded
    
    # Payment info
    payment_method = db.Column(db.String(50))
    payment_id = db.Column(db.String(100))  # External payment reference
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    # Foreign keys
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    items = db.relationship('OrderItem', backref='order', lazy='dynamic')
    
    def __repr__(self):
        return f'<Order {self.order_number}>'


class OrderItem(db.Model):
    """Individual items in an order"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Price at time of purchase (may differ from current price)
    price = db.Column(db.Float, nullable=False)
    
    # Foreign keys
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('study_material.id'), nullable=False)
    
    # Download tracking
    download_count = db.Column(db.Integer, default=0)
    last_download = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<OrderItem {self.material_id} in order {self.order_id}>'


class University(db.Model):
    """Universities for filtering"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    short_name = db.Column(db.String(20))
    country = db.Column(db.String(100))
    city = db.Column(db.String(100))
    
    def __repr__(self):
        return f'<University {self.name}>'


class Tag(db.Model):
    """Tags for study materials"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    
    def __repr__(self):
        return f'<Tag {self.name}>'


# Association table for material tags
material_tags = db.Table('material_tags',
    db.Column('material_id', db.Integer, db.ForeignKey('study_material.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

# Add relationship to StudyMaterial
StudyMaterial.tags = db.relationship('Tag', secondary=material_tags, backref='materials')
