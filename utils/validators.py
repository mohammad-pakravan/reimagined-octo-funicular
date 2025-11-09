"""
Validation utilities for user input.
Validates age, city, gender, and other profile data.
"""


def validate_age(age: int) -> tuple[bool, str]:
    """
    Validate user age.
    
    Args:
        age: Age to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(age, int):
        return False, "سن باید یک عدد باشد"
    
    if age < 13:
        return False, "حداقل سن 13 سال است"
    
    if age > 120:
        return False, "سن نامعتبر است. لطفاً سن معتبری وارد کنید."
    
    return True, ""


def validate_gender(gender: str) -> tuple[bool, str]:
    """
    Validate gender selection.
    
    Args:
        gender: Gender string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    valid_genders = ["male", "female", "other"]
    gender_lower = gender.lower().strip()
    
    if gender_lower not in valid_genders:
        return False, f"Invalid gender. Please choose from: {', '.join(valid_genders)}"
    
    return True, ""


def validate_city(city: str) -> tuple[bool, str]:
    """
    Validate city name.
    
    Args:
        city: City name to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not city or not isinstance(city, str):
        return False, "نام شهر نمی‌تواند خالی باشد"
    
    city = city.strip()
    
    if len(city) < 2:
        return False, "نام شهر باید حداقل 2 کاراکتر باشد"
    
    if len(city) > 100:
        return False, "نام شهر خیلی طولانی است. حداکثر 100 کاراکتر."
    
    # Basic validation: allow Persian/Arabic characters, spaces, hyphens, and apostrophes
    # More permissive validation for Persian cities
    if len(city) < 2:
        return False, "نام شهر باید حداقل 2 کاراکتر باشد"
    
    return True, ""


def validate_username(username: str) -> tuple[bool, str]:
    """
    Validate username.
    
    Args:
        username: Username to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not username or not isinstance(username, str):
        return False, "Username cannot be empty"
    
    username = username.strip()
    
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    
    if len(username) > 32:
        return False, "Username is too long. Maximum 32 characters."
    
    # Telegram username validation: alphanumeric and underscores
    if not username.replace("_", "").isalnum():
        return False, "Username can only contain letters, numbers, and underscores"
    
    return True, ""


def parse_age(text: str) -> tuple[bool, int, str]:
    """
    Parse age from text input.
    
    Args:
        text: Text input from user
        
    Returns:
        Tuple of (is_valid, age, error_message)
    """
    try:
        age = int(text.strip())
        is_valid, error_msg = validate_age(age)
        return is_valid, age, error_msg
    except ValueError:
        return False, 0, "سن باید یک عدد باشد. لطفاً سن معتبری وارد کنید."

