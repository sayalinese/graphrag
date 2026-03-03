"""
文档格式转换工具 - 采用多层回退策略
支持 .doc -> .docx 和 .xls -> .xlsx 的转换
线程安全的 Word/WPS COM 调用
"""

import os
import logging
import threading
import subprocess
import winreg
import sys
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, Tuple
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

# 线程锁：避免并发多次唤起 Word/WPS COM 造成崩溃
COM_WORD_LOCK = threading.Lock()


def _find_soffice_path() -> Optional[str]:
    """
    查找 LibreOffice soffice 可执行文件的完整路径
    """
    # 方法1：尝试从系统 PATH 直接调用
    import shutil
    soffice_exe = shutil.which('soffice.exe')
    if soffice_exe:
        return soffice_exe
    
    # 方法2：检查常见安装路径
    common_paths = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        r"C:\Program Files\LibreOffice 7.0\program\soffice.exe",
        r"C:\Program Files\LibreOffice 7.1\program\soffice.exe",
        r"C:\Program Files\LibreOffice 7.2\program\soffice.exe",
        r"C:\Program Files\LibreOffice 7.3\program\soffice.exe",
        r"C:\Program Files\LibreOffice 7.4\program\soffice.exe",
        r"C:\Program Files\LibreOffice 7.5\program\soffice.exe",
        r"C:\Program Files\LibreOffice 7.6\program\soffice.exe",
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            logger.info(f"Found LibreOffice at: {path}")
            return path
    
    return None


def detect_office_apps() -> dict:
    """
    检测系统中安装的 Office 应用
    返回: {'word': bool, 'wps': bool, 'libreoffice': bool}
    """
    apps = {'word': False, 'wps': False, 'libreoffice': False}
    
    # 检测 Microsoft Word
    try:
        import win32com.client
        word = win32com.client.Dispatch("Word.Application")
        word.Quit()
        apps['word'] = True
        logger.info("✓ Microsoft Word detected")
    except Exception:
        pass
    
    # 检测 WPS (金山)
    try:
        import win32com.client
        wps = win32com.client.Dispatch("kwps.Application")
        wps.Quit()
        apps['wps'] = True
        logger.info("✓ Kingsoft WPS detected")
    except Exception:
        pass
    
    # 检测 LibreOffice
    soffice_path = _find_soffice_path()
    if soffice_path:
        apps['libreoffice'] = True
        logger.info(f"✓ LibreOffice detected: {soffice_path}")
    
    return apps


@contextmanager
def temporary_converted_file(original_path: str, converter_func, ext_before: str, ext_after: str):
    """
    上下文管理器：执行文件转换，在 with 块结束后自动删除临时文件
    
    Args:
        original_path: 原始文件路径 (.doc 或 .xls)
        converter_func: 转换函数（返回转换后的文件路径）
        ext_before: 转换前的扩展名 (e.g., '.doc')
        ext_after: 转换后的扩展名 (e.g., '.docx')
    
    Yields:
        转换后的文件路径
    """
    converted_path = None
    try:
        if not original_path.lower().endswith(ext_before):
            raise ValueError(f"Expected {ext_before} file, got: {original_path}")
        
        converted_path = converter_func(original_path)
        yield converted_path
    finally:
        # 清理临时转换文件
        if converted_path and os.path.exists(converted_path):
            try:
                os.remove(converted_path)
                logger.info(f"Cleaned up temporary file: {converted_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up {converted_path}: {e}")


def convert_doc_to_docx(doc_path: str) -> str:
    """
    将 .doc 转为 .docx，优先级：
    1) LibreOffice (soffice) - 跨平台，最稳定，无对话框
    2) Microsoft Word (win32com) - 禁用对话框
    3) Kingsoft WPS (win32com) - 禁用对话框
    
    Args:
        doc_path: .doc 文件路径
        
    Returns:
        转换后的 .docx 文件路径
        
    Raises:
        ValueError: 转换失败
    """
    if not os.path.exists(doc_path):
        raise FileNotFoundError(f"File not found: {doc_path}")
    
    if not doc_path.lower().endswith('.doc'):
        raise ValueError(f"Expected .doc file, got: {doc_path}")
    
    # 处理文件名安全性
    file_dir = os.path.dirname(doc_path)
    file_name = os.path.splitext(os.path.basename(doc_path))[0]
    safe_name = secure_filename(file_name) or "doc_file"
    safe_doc_path = os.path.join(file_dir, f"{safe_name}.doc")
    
    if safe_doc_path != doc_path:
        try:
            import shutil
            shutil.copyfile(doc_path, safe_doc_path)
        except Exception as _copy_e:
            logger.warning(f"Copy .doc temp failed, use original: {_copy_e}")
            safe_doc_path = doc_path
    
    docx_path = os.path.join(file_dir, f"{safe_name}.docx")
    
    # 如果已存在则直接返回
    if os.path.exists(docx_path):
        logger.info(f"Converted file already exists: {docx_path}")
        return docx_path
    
    # 先删除已存在的 docx 文件（避免对话框提示覆盖）
    if os.path.exists(docx_path):
        try:
            os.remove(docx_path)
        except Exception:
            pass
    
    errors = {}
    
    # ===== 尝试 1: LibreOffice (soffice) - 优先 =====
    soffice_path = _find_soffice_path()
    if soffice_path:
        try:
            result = subprocess.run([
                soffice_path, '--headless', '--convert-to', 'docx', '--outdir', file_dir, safe_doc_path
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
            
            if result.returncode == 0 and os.path.exists(docx_path):
                logger.info(f"[DOC->DOCX] LibreOffice converted {safe_doc_path} -> {docx_path}")
                return docx_path
            else:
                errors['libreoffice'] = f"code={result.returncode}"
                logger.warning(f"[DOC->DOCX] LibreOffice returncode: {result.returncode}")
        except subprocess.TimeoutExpired:
            errors['libreoffice'] = "timeout (>60s)"
        except Exception as e:
            errors['libreoffice'] = str(e)
            logger.warning(f"[DOC->DOCX] LibreOffice failed: {e}")
    else:
        errors['libreoffice'] = "soffice not found"
    
    # ===== 尝试 2: Microsoft Word (win32com) - 禁用对话框 =====
    try:
        import pythoncom
        import win32com.client
        from win32com.client import constants
        
        with COM_WORD_LOCK:
            pythoncom.CoInitialize()
            word = None
            try:
                word = win32com.client.Dispatch("Word.Application")
                word.Visible = False
                # 禁用所有对话框和警告
                word.DisplayAlerts = constants.wdAlertsNone
                doc = word.Documents.Open(os.path.abspath(safe_doc_path), ConfirmConversions=False)
                # 保存前先删除目标文件
                if os.path.exists(docx_path):
                    os.remove(docx_path)
                doc.SaveAs2(docx_path, FileFormat=16)  # 16 = wdFormatDocx
                doc.Close(SaveChanges=constants.wdDoNotSaveChanges)
                logger.info(f"[DOC->DOCX] Microsoft Word converted {safe_doc_path} -> {docx_path}")
                return docx_path
            finally:
                try:
                    if word:
                        word.Quit(SaveChanges=constants.wdDoNotSaveChanges)
                except Exception:
                    pass
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
    except ImportError:
        errors['word'] = "win32com/pythoncom not installed"
    except Exception as e:
        errors['word'] = str(e)
        logger.warning(f"[DOC->DOCX] Microsoft Word failed: {e}")
    
    # ===== 尝试 3: Kingsoft WPS (win32com) - 禁用对话框 =====
    try:
        import pythoncom
        import win32com.client
        from win32com.client import constants
        
        with COM_WORD_LOCK:
            pythoncom.CoInitialize()
            wps = None
            try:
                wps = win32com.client.Dispatch("kwps.Application")
                wps.Visible = False
                # WPS 禁用对话框
                wps.DisplayAlerts = 0
                doc = wps.Documents.Open(os.path.abspath(safe_doc_path), ConfirmConversions=False)
                # 保存前先删除目标文件
                if os.path.exists(docx_path):
                    os.remove(docx_path)
                # WPS SaveAs: 第2参数是格式，8 = wdFormatDocx
                doc.SaveAs(docx_path, 8)
                doc.Close(0)  # 不保存
                logger.info(f"[DOC->DOCX] Kingsoft WPS converted {safe_doc_path} -> {docx_path}")
                return docx_path
            finally:
                try:
                    if wps:
                        wps.Quit(0)  # 不保存
                except Exception:
                    pass
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
    except ImportError:
        errors['wps'] = "win32com/pythoncom not installed"
    except Exception as e:
        errors['wps'] = str(e)
        logger.warning(f"[DOC->DOCX] Kingsoft WPS failed: {e}")
    
    # 清理临时安全 doc
    if safe_doc_path != doc_path and os.path.exists(safe_doc_path):
        try:
            os.remove(safe_doc_path)
        except Exception:
            pass
    
    # ===== 全部失败：抛出详细错误 =====
    detail_parts = []
    if 'libreoffice' in errors:
        detail_parts.append(f"  • LibreOffice: {errors['libreoffice']}")
    if 'word' in errors:
        detail_parts.append(f"  • Microsoft Word: {errors['word']}")
    if 'wps' in errors:
        detail_parts.append(f"  • Kingsoft WPS: {errors['wps']}")
    
    detail = "\n".join(detail_parts) if detail_parts else "No conversion method available"
    error_msg = (
        f"无法转换 .doc 文件。请尝试以下方案之一：\n\n"
        f"方案 1（推荐）：安装并配置 LibreOffice\n"
        f"  • 官网下载：https://www.libreoffice.org/download/\n"
        f"  • 安装后添加到系统 PATH（通常在 C:\\Program Files\\LibreOffice\\program）\n\n"
        f"方案 2：安装 Microsoft Word\n\n"
        f"方案 3：手动转换\n"
        f"  • 用 WPS/Word 打开此文件\n"
        f"  • 另存为 .docx 格式\n"
        f"  • 重新上传新文件\n\n"
        f"错误详情：\n{detail}"
    )
    logger.error(f"[DOC->DOCX] All conversion methods failed: {error_msg}")
    raise ValueError(error_msg)


def convert_xls_to_xlsx(xls_path: str) -> str:
    """
    将 .xls 文件转换为 .xlsx 文件，优先级：
    1) LibreOffice (soffice) - 跨平台，最稳定
    2) pandas + openpyxl 转换
    
    Args:
        xls_path: .xls 文件路径
        
    Returns:
        转换后的 .xlsx 文件路径
        
    Raises:
        ValueError: 转换失败
    """
    if not os.path.exists(xls_path):
        raise FileNotFoundError(f"File not found: {xls_path}")
    
    if not xls_path.lower().endswith('.xls'):
        raise ValueError(f"Expected .xls file, got: {xls_path}")
    
    # 处理文件名安全性
    file_dir = os.path.dirname(xls_path)
    file_name = os.path.splitext(os.path.basename(xls_path))[0]
    safe_name = secure_filename(file_name) or "xls_file"
    safe_xls_path = os.path.join(file_dir, f"{safe_name}.xls")
    
    if safe_xls_path != xls_path:
        try:
            import shutil
            shutil.copyfile(xls_path, safe_xls_path)
        except Exception as _copy_e:
            logger.warning(f"Copy .xls temp failed, use original: {_copy_e}")
            safe_xls_path = xls_path
    
    xlsx_path = os.path.join(file_dir, f"{safe_name}.xlsx")
    
    # 如果已存在则直接返回
    if os.path.exists(xlsx_path):
        logger.info(f"Converted file already exists: {xlsx_path}")
        return xlsx_path
    
    errors = {}
    
    # ===== 尝试 1: LibreOffice (soffice) - 优先 =====
    soffice_path = _find_soffice_path()
    if soffice_path:
        try:
            # 预先删除目标文件，避免弹出覆盖对话框
            if os.path.exists(xlsx_path):
                os.remove(xlsx_path)
            
            result = subprocess.run([
                soffice_path, '--headless', '--convert-to', 'xlsx', '--outdir', file_dir, safe_xls_path
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
            
            if result.returncode == 0 and os.path.exists(xlsx_path):
                logger.info(f"[XLS->XLSX] LibreOffice converted {safe_xls_path} -> {xlsx_path}")
                return xlsx_path
            else:
                errors['libreoffice'] = f"code={result.returncode}"
        except subprocess.TimeoutExpired:
            errors['libreoffice'] = "timeout (>60s)"
        except Exception as e:
            errors['libreoffice'] = str(e)
            logger.warning(f"[XLS->XLSX] LibreOffice failed: {e}")
    else:
        errors['libreoffice'] = "soffice not found in PATH or common installation paths"
    
    # ===== 尝试 2: Excel COM（Word COM 已配置，但 Excel 更稳定用于 .xls） =====
    try:
        import win32com.client  # type: ignore
        from win32com.client import constants
        
        with COM_WORD_LOCK:
            logger.info(f"[XLS->XLSX] Converting {safe_xls_path} to {xlsx_path} using Excel COM")
            
            # 预先删除目标文件，避免覆盖对话框
            if os.path.exists(xlsx_path):
                os.remove(xlsx_path)
            
            excel = win32com.client.Dispatch("Excel.Application")
            try:
                excel.DisplayAlerts = constants.xlAlertsNone  # Excel 常量：禁用所有警告
                workbook = excel.Workbooks.Open(safe_xls_path, ConfirmConversions=False)
                try:
                    # 保存为 .xlsx（FileFormat=51 = xlOpenXMLWorkbook）
                    workbook.SaveAs(xlsx_path, FileFormat=51)
                    if os.path.exists(xlsx_path):
                        logger.info(f"[XLS->XLSX] Excel COM converted {safe_xls_path} -> {xlsx_path}")
                        return xlsx_path
                finally:
                    workbook.Close(SaveChanges=constants.xlDoNotSaveChanges)  # 关闭不保存原文件
            finally:
                excel.Quit()  # 关闭 Excel 应用
    except ImportError:
        errors['excel_com'] = "win32com not installed"
    except Exception as e:
        errors['excel_com'] = str(e)
        logger.warning(f"[XLS->XLSX] Excel COM failed: {e}")
    
    # ===== 尝试 3: pandas + openpyxl =====
    try:
        import pandas as pd  # type: ignore
        logger.info(f"[XLS->XLSX] Converting {safe_xls_path} to {xlsx_path} using pandas")
        
        # 预先删除目标文件
        if os.path.exists(xlsx_path):
            os.remove(xlsx_path)
        
        # 读取所有工作表
        xls_file = pd.ExcelFile(safe_xls_path)
        
        # 写入为 .xlsx（openpyxl 格式）
        with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
            for sheet_name in xls_file.sheet_names:
                df = pd.read_excel(safe_xls_path, sheet_name=sheet_name, dtype=str)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        if os.path.exists(xlsx_path):
            logger.info(f"[XLS->XLSX] pandas converted {safe_xls_path} -> {xlsx_path}")
            return xlsx_path
    except ImportError:
        errors['pandas'] = "pandas/openpyxl not installed"
    except Exception as e:
        errors['pandas'] = str(e)
        logger.warning(f"[XLS->XLSX] pandas conversion failed: {e}")
    
    # 清理临时安全 xls
    if safe_xls_path != xls_path and os.path.exists(safe_xls_path):
        try:
            os.remove(safe_xls_path)
        except Exception:
            pass
    
    # ===== 全部失败：抛出详细错误 =====
    detail_parts = []
    if 'libreoffice' in errors:
        detail_parts.append(f"  • LibreOffice: {errors['libreoffice']}")
    if 'excel_com' in errors:
        detail_parts.append(f"  • Excel COM: {errors['excel_com']}")
    if 'pandas' in errors:
        detail_parts.append(f"  • pandas: {errors['pandas']}")
    
    detail = "\n".join(detail_parts) if detail_parts else "No conversion method available"
    error_msg = (
        f"无法转换 .xls 文件。请尝试以下方案之一：\n\n"
        f"方案 1（推荐）：安装并配置 LibreOffice\n"
        f"  • 官网下载：https://www.libreoffice.org/download/\n"
        f"  • 安装后添加到系统 PATH（通常在 C:\\Program Files\\LibreOffice\\program）\n\n"
        f"方案 2：安装 pandas 和 openpyxl\n"
        f"  • pip install pandas openpyxl xlrd\n\n"
        f"方案 3：手动转换\n"
        f"  • 用 Excel/WPS 打开此文件\n"
        f"  • 另存为 .xlsx 格式\n"
        f"  • 重新上传新文件\n\n"
        f"错误详情：\n{detail}"
    )
    logger.error(f"[XLS->XLSX] All conversion methods failed: {error_msg}")
    raise ValueError(error_msg)
