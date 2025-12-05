import os
import zipfile
from datetime import datetime
from flask import current_app
from pathlib import Path

class InvoiceStorageService:
    """Service for managing invoice ZIP file storage on disk"""
    
    @staticmethod
    def get_storage_base_path():
        """Get the base path for invoice storage"""
        try:
            storage_path = current_app.config.get('INVOICE_STORAGE_PATH', '/app/data/invoices')
            return storage_path
        except RuntimeError:
            # Not in app context - use environment variable or default
            import os
            return os.environ.get('INVOICE_STORAGE_PATH', '/app/data/invoices')
    
    @staticmethod
    def save_zip_file(company_id, invoice_id, zip_content, invoice_date=None):
        """
        Save ZIP file to disk with folder structure: invoices/{company_id}/{YYYY}/{MM}/{invoice_id}.zip
        
        Args:
            company_id: Company ID
            invoice_id: Invoice ID (ANAF ID)
            zip_content: Binary ZIP file content
            invoice_date: Invoice date (datetime.date or datetime) - used for folder structure
            
        Returns:
            str: Relative path to saved ZIP file (e.g., invoices/1/2025/01/invoice_123.zip)
            
        Raises:
            Exception: If file cannot be saved
        """
        try:
            base_path = InvoiceStorageService.get_storage_base_path()
            
            # Determine year and month from invoice_date or use current date
            if invoice_date:
                if isinstance(invoice_date, datetime):
                    year = invoice_date.year
                    month = invoice_date.month
                else:
                    # Assume it's a date object
                    year = invoice_date.year
                    month = invoice_date.month
            else:
                # Fallback to current date
                now = datetime.now()
                year = now.year
                month = now.month
            
            # Create folder structure: invoices/{company_id}/{YYYY}/{MM}/
            folder_path = os.path.join(base_path, str(company_id), str(year), f"{month:02d}")
            
            # Ensure directory exists
            Path(folder_path).mkdir(parents=True, exist_ok=True)
            
            # Sanitize invoice_id for filename
            safe_invoice_id = str(invoice_id).replace('/', '_').replace('\\', '_')
            filename = f"invoice_{safe_invoice_id}.zip"
            
            # Full path to ZIP file
            zip_file_path = os.path.join(folder_path, filename)
            
            # Write ZIP file
            with open(zip_file_path, 'wb') as f:
                f.write(zip_content)
            
            # Return relative path from base storage path
            relative_path = os.path.join(
                str(company_id), 
                str(year), 
                f"{month:02d}", 
                filename
            )
            
            try:
                current_app.logger.debug(f"Saved ZIP file: {relative_path}")
            except RuntimeError:
                pass  # Not in app context
            
            return relative_path
            
        except Exception as e:
            try:
                current_app.logger.error(f"Error saving ZIP file for invoice {invoice_id}: {str(e)}", exc_info=True)
            except RuntimeError:
                pass
            raise
    
    @staticmethod
    def get_zip_file_path(relative_path):
        """
        Get absolute path to saved ZIP file from relative path
        
        Args:
            relative_path: Relative path from storage base (e.g., invoices/1/2025/01/invoice_123.zip)
            
        Returns:
            str: Absolute path to ZIP file
        """
        base_path = InvoiceStorageService.get_storage_base_path()
        # Remove 'invoices/' prefix if present in relative_path
        if relative_path.startswith('invoices/'):
            relative_path = relative_path.replace('invoices/', '', 1)
        return os.path.join(base_path, relative_path)
    
    @staticmethod
    def zip_file_exists(relative_path):
        """
        Check if ZIP file exists on disk
        
        Args:
            relative_path: Relative path to ZIP file
            
        Returns:
            bool: True if file exists, False otherwise
        """
        try:
            absolute_path = InvoiceStorageService.get_zip_file_path(relative_path)
            return os.path.exists(absolute_path) and os.path.isfile(absolute_path)
        except Exception:
            return False
    
    @staticmethod
    def read_zip_file(relative_path):
        """
        Read ZIP file content from disk
        
        Args:
            relative_path: Relative path to ZIP file
            
        Returns:
            bytes: ZIP file content, or None if file doesn't exist
        """
        try:
            absolute_path = InvoiceStorageService.get_zip_file_path(relative_path)
            if os.path.exists(absolute_path) and os.path.isfile(absolute_path):
                with open(absolute_path, 'rb') as f:
                    return f.read()
            return None
        except Exception as e:
            try:
                current_app.logger.error(f"Error reading ZIP file {relative_path}: {str(e)}", exc_info=True)
            except RuntimeError:
                pass
            return None
    
    @staticmethod
    def delete_zip_file(relative_path):
        """
        Safely delete ZIP file from disk
        
        Args:
            relative_path: Relative path to ZIP file
            
        Returns:
            bool: True if file was deleted, False if it didn't exist or error occurred
        """
        try:
            absolute_path = InvoiceStorageService.get_zip_file_path(relative_path)
            if os.path.exists(absolute_path) and os.path.isfile(absolute_path):
                os.remove(absolute_path)
                try:
                    current_app.logger.debug(f"Deleted ZIP file: {relative_path}")
                except RuntimeError:
                    pass
                return True
            return False
        except Exception as e:
            try:
                current_app.logger.error(f"Error deleting ZIP file {relative_path}: {str(e)}", exc_info=True)
            except RuntimeError:
                pass
            return False
