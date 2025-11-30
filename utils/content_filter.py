"""
Content filtering utilities for detecting inappropriate text content.
Filters profanity and inappropriate words in Persian/Farsi text.
"""
import re
import json
import os
import logging
from typing import Tuple, List

logger = logging.getLogger(__name__)

# مسیر فایل لیست کلمات ممنوعه
PROFANITY_WORDS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'profanity_words.json')

# لیست پیش‌فرض کلمات ممنوعه (در صورت عدم وجود فایل)
DEFAULT_PROFANITY_WORDS = [
    "کص", "کس", "کوس", "کث", "کیر", "کصم", "کس میخوام", "کوس کث",
    "کیرم", "کصکش", "کسکش", "کوسکش",
    "جنده", "فاحشه", "فحش", "فحشا",
    "سکس", "سکسی", "سکس چت", "سکس ویدیو",
    "پورن", "پورنو", "پورنوگرافی",
    "ممه", "سینه", "پستان",
    "کون", "کونده", "کونکش",
    "لاشی", "لاش", "لاشخور",
    "ننه", "ننه جنده", "ننه کص",
    "بابات", "بابات کص",
    "خواهرت", "خواهرت کص",
    "مادر", "مادر جنده", "مادر کص",
    "پدر", "پدر سوخته",
    "حرومزاده", "حروم", "زاده",
    "لخت", "لخت کردن", "لخت شدن",
    "سکس کردن", "سکس چت کردن",
    "دختر سکسی", "دختر لخت",
    "پسر سکسی", "پسر لخت",
    "عکس لخت", "عکس سکسی",
    "ویدیو لخت", "ویدیو سکسی",
    "چت سکسی", "چت لخت",
    "دوست دختر", "دوست پسر",
    "دوستی سکسی", "ملاقات سکسی",
    "رابطه سکسی", "بوس سکسی",
    "بغل سکسی", "لمس سکسی",
    "نوازش سکسی", "ارضای جنسی",
    "ارگاسم", "ارگاسمی",
]


def load_profanity_words() -> List[str]:
    """
    Load profanity words from JSON file, or use default list if file doesn't exist.
    
    Returns:
        List of profanity words
    """
    try:
        if os.path.exists(PROFANITY_WORDS_FILE):
            with open(PROFANITY_WORDS_FILE, 'r', encoding='utf-8') as f:
                words = json.load(f)
                logger.info(f"Loaded {len(words)} profanity words from {PROFANITY_WORDS_FILE}")
                return words
        else:
            logger.warning(f"Profanity words file not found at {PROFANITY_WORDS_FILE}, using default list")
            return DEFAULT_PROFANITY_WORDS
    except Exception as e:
        logger.error(f"Error loading profanity words file: {e}", exc_info=True)
        logger.warning("Using default profanity words list")
        return DEFAULT_PROFANITY_WORDS


# لیست کلمات ممنوعه (بارگذاری از فایل یا استفاده از پیش‌فرض)
PROFANITY_WORDS = load_profanity_words()

# کاراکترهای جایگزین رایج برای دور زدن فیلتر
CHAR_REPLACEMENTS = {
    'ص': ['س', 'ث', 'ص'],
    'س': ['ص', 'ث', 'س'],
    'ث': ['ص', 'س', 'ث'],
    'ک': ['ک', 'ك', 'ک'],
    'ی': ['ی', 'ي', 'ی', 'ئ'],
    'ا': ['ا', 'آ', 'أ', 'إ'],
    'ه': ['ه', 'ة', 'ه'],
    'ز': ['ز', 'ظ', 'ض', 'ذ'],
    'ظ': ['ز', 'ظ', 'ض', 'ذ'],
    'ض': ['ز', 'ظ', 'ض', 'ذ'],
    'ذ': ['ز', 'ظ', 'ض', 'ذ'],
    'ت': ['ت', 'ط'],
    'ط': ['ت', 'ط'],
    'غ': ['غ', 'ق'],
    'ق': ['غ', 'ق'],
    'ح': ['ح', 'ه'],
    'خ': ['خ', 'ح'],
    'ج': ['ج', 'چ'],
    'چ': ['ج', 'چ'],
    'ش': ['ش', 'س'],
    'ع': ['ع', 'ا'],
    'ف': ['ف', 'پ'],
    'پ': ['ف', 'پ'],
    'ب': ['ب', 'پ'],
    'م': ['م', 'ن'],
    'ن': ['م', 'ن'],
    'ل': ['ل', 'ر'],
    'ر': ['ل', 'ر'],
    'و': ['و', 'ؤ'],
    'د': ['د', 'ذ'],
    'گ': ['گ', 'ک'],
    'ژ': ['ژ', 'ز'],
}


def normalize_text(text: str) -> str:
    """
    Normalize text by removing special characters and converting to standard form.
    
    Args:
        text: Input text to normalize
        
    Returns:
        Normalized text
    """
    if not text:
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove common special characters used to bypass filters
    text = re.sub(r'[^\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFFa-z0-9\s]', '', text)
    
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing spaces
    text = text.strip()
    
    return text


def generate_variations(word: str) -> List[str]:
    """
    Generate variations of a word by replacing characters with similar ones.
    
    Args:
        word: Word to generate variations for
        
    Returns:
        List of possible variations
    """
    variations = [word]
    
    # Generate variations by replacing each character with similar ones
    for i, char in enumerate(word):
        if char in CHAR_REPLACEMENTS:
            for replacement in CHAR_REPLACEMENTS[char]:
                if replacement != char:
                    variation = word[:i] + replacement + word[i+1:]
                    if variation not in variations:
                        variations.append(variation)
    
    return variations


def check_profanity(text: str) -> Tuple[bool, str]:
    """
    Check if text contains profanity words.
    
    Args:
        text: Text to check
        
    Returns:
        Tuple of (contains_profanity, matched_word)
    """
    normalized = normalize_text(text)
    
    # Check against direct profanity words
    for word in PROFANITY_WORDS:
        normalized_word = normalize_text(word)
        if normalized_word in normalized:
            return True, word
    
    # Check against variations
    for word in PROFANITY_WORDS:
        normalized_word = normalize_text(word)
        variations = generate_variations(normalized_word)
        
        for variation in variations:
            if variation in normalized:
                return True, word
    
    return False, ""


def detect_pattern(text: str) -> Tuple[bool, str]:
    """
    Detect inappropriate patterns in text (e.g., "کس میخوام", "کصم").
    
    Args:
        text: Text to check
        
    Returns:
        Tuple of (contains_pattern, matched_pattern)
    """
    normalized = normalize_text(text)
    
    # Common inappropriate patterns
    patterns = [
        r'کس\s*میخوام',
        r'کص\s*میخوام',
        r'کوس\s*میخوام',
        r'کث\s*میخوام',
        r'کیر\s*میخوام',
        r'کصم',
        r'کس\s*میخوای',
        r'کص\s*میخوای',
        r'کوس\s*میخوای',
        r'کث\s*میخوای',
        r'کیر\s*میخوای',
        r'کس\s*بخواه',
        r'کص\s*بخواه',
        r'کوس\s*بخواه',
        r'کث\s*بخواه',
        r'کیر\s*بخواه',
        r'کس\s*بخوای',
        r'کص\s*بخوای',
        r'کوس\s*بخوای',
        r'کث\s*بخوای',
        r'کیر\s*بخوای',
        r'کس\s*بخو',
        r'کص\s*بخو',
        r'کوس\s*بخو',
        r'کث\s*بخو',
        r'کیر\s*بخو',
        r'کس\s*بخ',
        r'کص\s*بخ',
        r'کوس\s*بخ',
        r'کث\s*بخ',
        r'کیر\s*بخ',
        r'کس\s*می',
        r'کص\s*می',
        r'کوس\s*می',
        r'کث\s*می',
        r'کیر\s*می',
        r'کس\s*م',
        r'کص\s*م',
        r'کوس\s*م',
        r'کث\s*م',
        r'کیر\s*م',
        r'کس\s*ک',
        r'کص\s*ک',
        r'کوس\s*ک',
        r'کث\s*ک',
        r'کیر\s*ک',
        r'کس\s*کش',
        r'کص\s*کش',
        r'کوس\s*کش',
        r'کث\s*کش',
        r'کیر\s*کش',
        r'کس\s*کش',
        r'کص\s*کش',
        r'کوس\s*کش',
        r'کث\s*کش',
        r'کیر\s*کش',
    ]
    
    for pattern in patterns:
        if re.search(pattern, normalized, re.IGNORECASE):
            return True, pattern
    
    return False, ""


def validate_display_name(display_name: str) -> Tuple[bool, str]:
    """
    Validate display name for inappropriate content.
    
    Args:
        display_name: Display name to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not display_name:
        return False, "نام نمایشی نمی‌تواند خالی باشد"
    
    # Check for profanity
    has_profanity, matched_word = check_profanity(display_name)
    if has_profanity:
        logger.warning(f"Profanity detected in display name: {matched_word}")
        return False, "❌ نام نمایشی شما حاوی محتوای نامناسب است. لطفاً نام مناسب‌تری انتخاب کنید."
    
    # Check for patterns
    has_pattern, matched_pattern = detect_pattern(display_name)
    if has_pattern:
        logger.warning(f"Inappropriate pattern detected in display name: {matched_pattern}")
        return False, "❌ نام نمایشی شما حاوی محتوای نامناسب است. لطفاً نام مناسب‌تری انتخاب کنید."
    
    return True, ""

