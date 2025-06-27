#!/bin/bash

# F5 LLM推理网关调度器日志管理脚本
# 用于传统部署环境的日志压缩、归档和清理

set -e

# 配置变量（支持环境变量覆盖）
LOG_DIR="${F5_SCHEDULER_LOG_DIR:-/opt/f5-scheduler/logs}"
ARCHIVE_DIR="${F5_SCHEDULER_ARCHIVE_DIR:-${LOG_DIR}/archive}"
LOG_FILE="${F5_SCHEDULER_LOG_FILE:-scheduler.log}"
RETENTION_DAYS="${F5_SCHEDULER_RETENTION_DAYS:-30}"
COMPRESS_DAYS="${F5_SCHEDULER_COMPRESS_DAYS:-7}"
MAX_LOG_SIZE="${F5_SCHEDULER_MAX_LOG_SIZE:-100M}"

# 自动检测日志路径（从环境变量LOG_FILE_PATH）
if [ -n "$LOG_FILE_PATH" ] && [ "$LOG_FILE_PATH" != "" ]; then
    LOG_DIR=$(dirname "$LOG_FILE_PATH")
    LOG_FILE=$(basename "$LOG_FILE_PATH")
    ARCHIVE_DIR="${LOG_DIR}/archive"
    echo "检测到LOG_FILE_PATH环境变量，使用路径: $LOG_FILE_PATH"
fi

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# 显示当前配置
show_config() {
    echo "=================================="
    echo "F5 Scheduler 日志管理配置"
    echo "=================================="
    echo "日志目录: $LOG_DIR"
    echo "日志文件: $LOG_FILE"
    echo "归档目录: $ARCHIVE_DIR"
    echo "保留天数: $RETENTION_DAYS"
    echo "压缩天数: $COMPRESS_DAYS"
    echo "最大大小: $MAX_LOG_SIZE"
    echo "=================================="
}

# 检查目录是否存在
check_directories() {
    if [ ! -d "$LOG_DIR" ]; then
        log_error "日志目录不存在: $LOG_DIR"
        log_info "尝试创建日志目录..."
        mkdir -p "$LOG_DIR" || {
            log_error "无法创建日志目录: $LOG_DIR"
            exit 1
        }
        log_success "日志目录创建成功: $LOG_DIR"
    fi
    
    if [ ! -d "$ARCHIVE_DIR" ]; then
        log_info "创建归档目录: $ARCHIVE_DIR"
        mkdir -p "$ARCHIVE_DIR"
    fi
}

# 自动检测日志文件
detect_log_files() {
    local log_file_path="$LOG_DIR/$LOG_FILE"
    
    if [ ! -f "$log_file_path" ]; then
        log_warn "指定的日志文件不存在: $log_file_path"
        
        # 尝试查找可能的日志文件
        local found_files=$(find "$LOG_DIR" -name "*.log" -type f 2>/dev/null | head -5)
        if [ -n "$found_files" ]; then
            log_info "在日志目录中找到以下日志文件："
            echo "$found_files" | while read -r file; do
                local size=$(du -h "$file" 2>/dev/null | cut -f1 || echo "unknown")
                echo "  - $(basename "$file") (大小: $size)"
            done
        else
            log_warn "在 $LOG_DIR 中未找到任何 .log 文件"
        fi
        return 1
    fi
    return 0
}

# 检查日志文件大小并轮转
rotate_log_by_size() {
    local log_file="$LOG_DIR/$LOG_FILE"
    
    if ! detect_log_files; then
        return
    fi
    
    # 检查文件大小
    local file_size=$(du -h "$log_file" | cut -f1)
    local size_bytes=$(stat -c%s "$log_file")
    local max_bytes=104857600  # 100MB
    
    # 支持不同的大小单位
    case "${MAX_LOG_SIZE^^}" in
        *K|*KB) max_bytes=$((${MAX_LOG_SIZE%[Kk]*} * 1024)) ;;
        *M|*MB) max_bytes=$((${MAX_LOG_SIZE%[Mm]*} * 1024 * 1024)) ;;
        *G|*GB) max_bytes=$((${MAX_LOG_SIZE%[Gg]*} * 1024 * 1024 * 1024)) ;;
        *) max_bytes=104857600 ;;  # 默认100MB
    esac
    
    if [ "$size_bytes" -gt "$max_bytes" ]; then
        log_info "日志文件大小 ($file_size) 超过限制 ($MAX_LOG_SIZE)，开始轮转..."
        
        # 生成时间戳
        local timestamp=$(date '+%Y%m%d_%H%M%S')
        local rotated_file="$LOG_DIR/scheduler_${timestamp}.log"
        
        # 复制并截断原文件（copytruncate方式）
        cp "$log_file" "$rotated_file"
        > "$log_file"
        
        log_success "日志文件已轮转: $rotated_file"
        
        # 立即压缩新轮转的文件
        compress_single_file "$rotated_file"
    else
        log_info "日志文件大小 ($file_size) 未超过限制 ($MAX_LOG_SIZE)，无需轮转"
    fi
}

# 压缩单个文件
compress_single_file() {
    local file_path="$1"
    
    if [ -f "$file_path" ]; then
        log_info "压缩文件: $file_path"
        gzip "$file_path"
        log_success "文件压缩完成: ${file_path}.gz"
    fi
}

# 压缩旧日志文件
compress_old_logs() {
    log_info "开始压缩 $COMPRESS_DAYS 天前的日志文件..."
    
    # 查找需要压缩的文件
    local files_to_compress=$(find "$LOG_DIR" -name "scheduler_*.log" -type f -mtime +$COMPRESS_DAYS 2>/dev/null)
    
    if [ -z "$files_to_compress" ]; then
        log_info "没有找到需要压缩的日志文件"
        return
    fi
    
    # 压缩文件
    echo "$files_to_compress" | while read -r file; do
        if [ -f "$file" ]; then
            compress_single_file "$file"
        fi
    done
}

# 归档压缩文件
archive_compressed_logs() {
    log_info "开始归档压缩的日志文件..."
    
    # 移动压缩文件到归档目录
    local compressed_files=$(find "$LOG_DIR" -name "scheduler_*.log.gz" -type f -maxdepth 1 2>/dev/null)
    
    if [ -z "$compressed_files" ]; then
        log_info "没有找到需要归档的压缩文件"
        return
    fi
    
    echo "$compressed_files" | while read -r file; do
        if [ -f "$file" ]; then
            local filename=$(basename "$file")
            mv "$file" "$ARCHIVE_DIR/"
            log_success "文件已归档: $ARCHIVE_DIR/$filename"
        fi
    done
}

# 清理过期文件
cleanup_old_archives() {
    log_info "开始清理 $RETENTION_DAYS 天前的归档文件..."
    
    # 查找过期文件
    local old_files=$(find "$ARCHIVE_DIR" -name "scheduler_*.log.gz" -type f -mtime +$RETENTION_DAYS 2>/dev/null)
    
    if [ -z "$old_files" ]; then
        log_info "没有找到需要清理的过期文件"
        return
    fi
    
    # 删除过期文件
    local deleted_count=0
    echo "$old_files" | while read -r file; do
        if [ -f "$file" ]; then
            local file_size=$(du -h "$file" | cut -f1)
            rm "$file"
            log_success "已删除过期文件: $(basename "$file") (大小: $file_size)"
            ((deleted_count++))
        fi
    done
    
    if [ "$deleted_count" -gt 0 ]; then
        log_success "共清理了 $deleted_count 个过期文件"
    fi
}

# 生成日志统计报告
generate_log_report() {
    log_info "生成日志统计报告..."
    
    echo "=================================="
    echo "F5 Scheduler 日志统计报告"
    echo "生成时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=================================="
    
    # 当前配置信息
    echo "配置信息:"
    echo "  - 日志目录: $LOG_DIR"
    echo "  - 日志文件: $LOG_FILE"
    echo "  - 归档目录: $ARCHIVE_DIR"
    
    # 当前日志文件信息
    local log_file_path="$LOG_DIR/$LOG_FILE"
    if [ -f "$log_file_path" ]; then
        local current_size=$(du -h "$log_file_path" | cut -f1)
        local current_lines=$(wc -l < "$log_file_path")
        local last_modified=$(stat -c %y "$log_file_path" | cut -d. -f1)
        echo "当前日志文件:"
        echo "  - 文件: $LOG_FILE"
        echo "  - 大小: $current_size"
        echo "  - 行数: $current_lines"
        echo "  - 最后修改: $last_modified"
    else
        echo "当前日志文件: 不存在"
    fi
    
    # 归档文件统计
    if [ -d "$ARCHIVE_DIR" ]; then
        local archive_count=$(find "$ARCHIVE_DIR" -name "scheduler_*.log.gz" -type f 2>/dev/null | wc -l)
        local archive_size=$(du -sh "$ARCHIVE_DIR" 2>/dev/null | cut -f1 || echo "0")
        
        echo "归档文件统计:"
        echo "  - 文件数量: $archive_count"
        echo "  - 总大小: $archive_size"
        
        # 显示最新的几个归档文件
        if [ "$archive_count" -gt 0 ]; then
            echo "  - 最新归档文件:"
            find "$ARCHIVE_DIR" -name "scheduler_*.log.gz" -type f -printf "    %f (%s bytes, %TY-%Tm-%Td)\n" 2>/dev/null | sort -r | head -3
        fi
    else
        echo "归档目录: 不存在"
    fi
    
    # 磁盘使用情况
    echo "磁盘使用情况:"
    if [ -d "$LOG_DIR" ]; then
        df -h "$LOG_DIR" | tail -n 1 | awk '{print "  - 可用空间: " $4 " / " $2 " (" $5 " 已使用)"}'
    else
        echo "  - 日志目录不存在"
    fi
    
    echo "=================================="
}

# 生成logrotate配置
generate_logrotate_config() {
    local config_file="${1:-/tmp/f5-scheduler-logrotate.conf}"
    local log_file_path="$LOG_DIR/$LOG_FILE"
    
    log_info "生成logrotate配置文件: $config_file"
    
    cat > "$config_file" << EOF
# F5 LLM推理网关调度器日志轮转配置
# 自动生成于 $(date)
# 日志路径: $log_file_path

$log_file_path {
    daily
    rotate 30
    missingok
    notifempty
    compress
    delaycompress
    dateext
    dateformat -%Y%m%d
    create 644 scheduler scheduler
    size $MAX_LOG_SIZE
    copytruncate
    
    postrotate
        logger -t f5-scheduler "Log rotation completed for $log_file_path"
    endscript
}
EOF
    
    log_success "logrotate配置文件已生成: $config_file"
    log_info "使用方法: sudo cp $config_file /etc/logrotate.d/f5-scheduler"
}

# 主函数
main() {
    local action="${1:-all}"
    
    # 首先显示配置信息
    if [ "$action" != "help" ] && [ "$action" != "-h" ] && [ "$action" != "--help" ]; then
        show_config
        echo ""
    fi
    
    case "$action" in
        "config")
            show_config
            ;;
        "detect")
            log_info "检测日志文件..."
            check_directories
            detect_log_files && log_success "日志文件检测正常" || log_warn "日志文件检测发现问题"
            ;;
        "rotate")
            log_info "执行日志轮转..."
            check_directories
            rotate_log_by_size
            ;;
        "compress")
            log_info "执行日志压缩..."
            check_directories
            compress_old_logs
            ;;
        "archive")
            log_info "执行日志归档..."
            check_directories
            archive_compressed_logs
            ;;
        "cleanup")
            log_info "执行清理操作..."
            check_directories
            cleanup_old_archives
            ;;
        "report")
            check_directories
            generate_log_report
            ;;
        "logrotate")
            local output_file="${2:-/tmp/f5-scheduler-logrotate.conf}"
            check_directories
            generate_logrotate_config "$output_file"
            ;;
        "all")
            log_info "执行完整的日志管理流程..."
            check_directories
            rotate_log_by_size
            compress_old_logs
            archive_compressed_logs
            cleanup_old_archives
            generate_log_report
            ;;
        "help"|"-h"|"--help")
            echo "F5 Scheduler 日志管理脚本"
            echo ""
            echo "用法: $0 [操作] [参数]"
            echo ""
            echo "操作:"
            echo "  config    - 显示当前配置"
            echo "  detect    - 检测日志文件状态"
            echo "  rotate    - 按大小轮转当前日志文件"
            echo "  compress  - 压缩旧日志文件"
            echo "  archive   - 归档压缩文件"
            echo "  cleanup   - 清理过期归档文件"
            echo "  report    - 生成日志统计报告"
            echo "  logrotate [文件] - 生成logrotate配置文件"
            echo "  all       - 执行所有操作 (默认)"
            echo "  help      - 显示帮助信息"
            echo ""
            echo "环境变量配置:"
            echo "  F5_SCHEDULER_LOG_DIR      - 日志目录 (默认: /opt/f5-scheduler/logs)"
            echo "  F5_SCHEDULER_LOG_FILE     - 日志文件名 (默认: scheduler.log)"
            echo "  F5_SCHEDULER_ARCHIVE_DIR  - 归档目录 (默认: \$LOG_DIR/archive)"
            echo "  F5_SCHEDULER_RETENTION_DAYS - 保留天数 (默认: 30)"
            echo "  F5_SCHEDULER_COMPRESS_DAYS  - 压缩天数 (默认: 7)"
            echo "  F5_SCHEDULER_MAX_LOG_SIZE   - 最大文件大小 (默认: 100M)"
            echo "  LOG_FILE_PATH             - 完整日志文件路径 (自动解析目录和文件名)"
            echo ""
            echo "示例:"
            echo "  # 使用环境变量指定日志路径"
            echo "  LOG_FILE_PATH=/var/log/scheduler.log $0 all"
            echo ""
            echo "  # 生成适配当前路径的logrotate配置"
            echo "  $0 logrotate /tmp/my-logrotate.conf"
            ;;
        *)
            log_error "未知操作: $action"
            echo "使用 '$0 help' 查看帮助信息"
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@" 