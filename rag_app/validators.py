"""
文件验证模块
提供文件上传的安全验证功能
"""
import io
import logging
import mimetypes
from pathlib import Path
from typing import BinaryIO

from rag_app import config
from rag_app.exceptions import FileValidationError

logger = logging.getLogger(__name__)


def validate_file_extension(filename: str) -> str:
    """
    验证文件扩展名
    
    Args:
        filename: 文件名
        
    Returns:
        标准化的文件扩展名(小写,不含点)
        
    Raises:
        FileValidationError: 扩展名不支持
    """
    file_suffix = Path(filename).suffix.lower().lstrip(".")
    
    if not file_suffix:
        raise FileValidationError(
            "文件缺少扩展名",
            filename=filename,
            validation_type="extension"
        )
    
    if file_suffix not in config.SUPPORTED_UPLOAD_EXTENSIONS:
        raise FileValidationError(
            f"不支持的文件格式: {file_suffix}。支持的格式: {', '.join(config.SUPPORTED_UPLOAD_EXTENSIONS)}",
            filename=filename,
            validation_type="extension"
        )
    
    return file_suffix


def validate_filename_safety(filename: str) -> str:
    """
    验证文件名安全性,防止路径遍历攻击
    
    Args:
        filename: 文件名
        
    Returns:
        清理后的安全文件名
        
    Raises:
        FileValidationError: 文件名不安全
    """
    # 只保留文件名部分,移除任何路径
    safe_filename = Path(filename).name
    
    # 二次检查:移除所有路径分隔符
    safe_filename = safe_filename.replace('/', '').replace('\\', '').replace('\0', '')
    
    # 检查是否包含路径遍历字符
    if ".." in safe_filename:
        raise FileValidationError(
            "文件名包含非法路径字符",
            filename=filename,
            validation_type="filename_safety"
        )
    
    # 验证文件名只包含安全字符
    # 允许: 字母、数字、中文、下划线、连字符、点、空格、括号
    import re
    if not re.match(r'^[\w\-\.\u4e00-\u9fa5\s\(\)（）]+$', safe_filename):
        raise FileValidationError(
            "文件名包含非法字符,请使用字母、数字、中文、下划线、连字符",
            filename=filename,
            validation_type="filename_safety"
        )
    
    # 限制文件名长度
    if len(safe_filename) > 255:
        raise FileValidationError(
            "文件名过长,最多255个字符",
            filename=filename,
            validation_type="filename_length"
        )
    
    return safe_filename


def validate_file_magic_bytes(file_content: bytes | BinaryIO, filename: str, extension: str) -> bool:
    """
    验证文件魔数(Magic Bytes),确保文件内容与扩展名匹配
    
    Args:
        file_content: 文件内容或文件对象
        filename: 文件名
        extension: 文件扩展名
        
    Returns:
        验证是否通过
        
    Raises:
        FileValidationError: 文件内容与扩展名不匹配
    """
    # 读取文件头部字节(读取更多字节以支持更多格式)
    if isinstance(file_content, bytes):
        header = file_content[:512]  # 读取512字节
    else:
        current_pos = file_content.tell()
        file_content.seek(0)
        header = file_content.read(512)  # 读取512字节
        file_content.seek(current_pos)
    
    if not header:
        raise FileValidationError(
            "文件内容为空",
            filename=filename,
            validation_type="magic_bytes"
        )
    
    # 检查文件魔数
    signatures = config.FILE_MAGIC_SIGNATURES.get(extension, [])
    
    # 文本文件不需要魔数验证
    if extension in ["txt", "md", "csv"]:
        # 验证是否为有效的文本内容(支持多种编码)
        try:
            if isinstance(file_content, bytes):
                # 尝试多种常见编码
                for encoding in ['utf-8', 'gbk', 'gb2312', 'utf-16', 'latin-1']:
                    try:
                        header.decode(encoding)
                        return True
                    except (UnicodeDecodeError, LookupError):
                        continue
                # 所有编码都失败
                raise UnicodeDecodeError('multiple', b'', 0, 1, 'all encodings failed')
            return True
        except UnicodeDecodeError:
            raise FileValidationError(
                f"文件内容不是有效的文本格式",
                filename=filename,
                validation_type="magic_bytes"
            )
    
    # 验证二进制文件魔数
    if signatures:
        for signature in signatures:
            if header.startswith(signature):
                return True
        
        raise FileValidationError(
            f"文件内容与扩展名 .{extension} 不匹配,可能是伪装的恶意文件",
            filename=filename,
            validation_type="magic_bytes"
        )
    
    # 没有配置魔数的文件类型,跳过验证
    logger.warning(f"文件类型 {extension} 没有配置魔数验证")
    return True


def validate_file_size(size_bytes: int, filename: str) -> bool:
    """
    验证文件大小
    
    Args:
        size_bytes: 文件大小(字节)
        filename: 文件名
        
    Returns:
        验证是否通过
        
    Raises:
        FileValidationError: 文件大小不符合要求
    """
    if size_bytes <= 0:
        raise FileValidationError(
            "空文件无法导入知识库",
            filename=filename,
            validation_type="file_size"
        )
    
    if size_bytes > config.MAX_UPLOAD_FILE_SIZE_BYTES:
        raise FileValidationError(
            f"单个文件不能超过 {config.MAX_UPLOAD_FILE_SIZE_MB} MB",
            filename=filename,
            validation_type="file_size"
        )
    
    return True


def validate_mime_type(file_content: bytes | BinaryIO, filename: str, extension: str) -> bool:
    """
    验证MIME类型
    
    Args:
        file_content: 文件内容或文件对象
        filename: 文件名
        extension: 文件扩展名
        
    Returns:
        验证是否通过
    """
    # 基于扩展名猜测MIME类型
    expected_mime, _ = mimetypes.guess_type(filename)
    
    if not expected_mime:
        logger.debug(f"无法确定文件 {filename} 的MIME类型")
        return True
    
    # 这里可以添加更复杂的MIME类型检测逻辑
    # 例如使用python-magic库
    
    return True


def validate_upload_file(
    file_content: bytes | BinaryIO,
    filename: str,
    size_bytes: int,
    skip_magic_bytes: bool = False
) -> tuple[str, str]:
    """
    完整的文件上传验证流程
    
    Args:
        file_content: 文件内容或文件对象
        filename: 文件名
        size_bytes: 文件大小
        skip_magic_bytes: 是否跳过魔数验证(用于测试)
        
    Returns:
        (安全的文件名, 文件扩展名)
        
    Raises:
        FileValidationError: 验证失败
    """
    # 1. 验证文件名安全性
    safe_filename = validate_filename_safety(filename)
    
    # 2. 验证文件扩展名
    extension = validate_file_extension(safe_filename)
    
    # 3. 验证文件大小
    validate_file_size(size_bytes, safe_filename)
    
    # 4. 验证文件魔数
    if not skip_magic_bytes:
        validate_file_magic_bytes(file_content, safe_filename, extension)
    
    # 5. 验证MIME类型
    validate_mime_type(file_content, safe_filename, extension)
    
    return safe_filename, extension
