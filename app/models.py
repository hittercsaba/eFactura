from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
from sqlalchemy.orm import relationship

db = SQLAlchemy()
migrate = Migrate()

class User(UserMixin, db.Model):
    """User model - account holders"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    oauth_config = relationship('AnafOAuthConfig', back_populates='user', uselist=False)
    anaf_token = relationship('AnafToken', back_populates='user', uselist=False)
    companies = relationship('Company', back_populates='user', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.email}>'


class AnafOAuthConfig(db.Model):
    """OAuth configuration per user/client"""
    __tablename__ = 'anaf_oauth_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    client_id = db.Column(db.String(255), nullable=False)
    client_secret = db.Column(db.String(255), nullable=False)
    redirect_uri = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    user = relationship('User', back_populates='oauth_config')
    
    def __repr__(self):
        return f'<AnafOAuthConfig user_id={self.user_id}>'


class AnafToken(db.Model):
    """ANAF OAuth tokens - one per user"""
    __tablename__ = 'anaf_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    access_token = db.Column(db.String(500), nullable=False)
    refresh_token = db.Column(db.String(500), nullable=True)
    token_expiry = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    user = relationship('User', back_populates='anaf_token')
    
    def is_expired(self):
        """Check if token is expired"""
        if not self.token_expiry:
            return False
        return datetime.now(timezone.utc) >= self.token_expiry
    
    def __repr__(self):
        return f'<AnafToken user_id={self.user_id}>'


class Company(db.Model):
    """Company model - multiple companies per user"""
    __tablename__ = 'companies'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    cif = db.Column(db.String(20), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.Text, nullable=True)
    auto_sync_enabled = db.Column(db.Boolean, default=True, nullable=False)
    sync_interval_hours = db.Column(db.Integer, default=24, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Unique constraint: same CIF can't be added twice for same user
    __table_args__ = (db.UniqueConstraint('user_id', 'cif', name='unique_user_cif'),)
    
    # Relationships
    user = relationship('User', back_populates='companies')
    invoices = relationship('Invoice', back_populates='company', cascade='all, delete-orphan')
    api_keys = relationship('ApiKey', back_populates='company', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Company {self.cif} - {self.name}>'


class ApiKey(db.Model):
    """API keys - issued per company"""
    __tablename__ = 'api_keys'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    key_hash = db.Column(db.String(255), unique=True, nullable=False, index=True)  # Increased from 128 to 255 for longer hashes
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_used_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    company = relationship('Company', back_populates='api_keys')
    
    def update_last_used(self):
        """Update last used timestamp"""
        self.last_used_at = datetime.now(timezone.utc)
        db.session.commit()
    
    def __repr__(self):
        return f'<ApiKey company_id={self.company_id} active={self.is_active}>'


class Invoice(db.Model):
    """Invoice model - synced from ANAF"""
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    anaf_id = db.Column(db.String(100), nullable=False, index=True)
    supplier_name = db.Column(db.String(200), nullable=True)
    supplier_cif = db.Column(db.String(20), nullable=True)
    invoice_date = db.Column(db.Date, nullable=True)
    total_amount = db.Column(db.Numeric(15, 2), nullable=True)
    xml_content = db.Column(db.Text, nullable=False)
    json_content = db.Column(db.JSON, nullable=True)
    synced_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Unique constraint: same ANAF ID can't be synced twice for same company
    __table_args__ = (db.UniqueConstraint('company_id', 'anaf_id', name='unique_company_anaf_id'),)
    
    # Relationships
    company = relationship('Company', back_populates='invoices')
    
    def __repr__(self):
        return f'<Invoice {self.anaf_id} - {self.supplier_name}>'

