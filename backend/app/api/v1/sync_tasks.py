"""鍚屾浠诲姟绠＄悊鎺ュ彛锛圴2.0 灞傜骇涓€ - API 璧勪骇搴擄級
绗﹀悎鍚庣浠ｇ爜瑙勮寖锛?
1. 缁熶竴鍝嶅簲浣擄細{ code, message, data }
2. IDOR 闃插尽锛氭牎楠岃祫婧愬綊灞?
3. 鍏ㄩ摼璺?TraceID锛氫娇鐢?get_trace_id()
4. 榄旀硶鍊兼竻鐞嗭細浣跨敤鏋氫妇瀹氫箟鐘舵€?
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
import logging

from app.dependencies import get_db
from app.context import get_current_project_id
from app.platform.db.base import SyncTask, User, ApiDefinition
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id

router = APIRouter()
logger = logging.getLogger(__name__)


# ========== 鏋氫妇瀹氫箟锛堥伩鍏嶉瓟娉曞€硷級 ==========

class SyncTaskStatus(str):
    """鍚屾浠诲姟鐘舵€佹灇涓?""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SourceType(str):
    """鏂囨。鏉ユ簮绫诲瀷鏋氫妇"""
    SWAGGER = "swagger"
    POSTMAN = "postman"
    YAPI = "yapi"
    MANUAL = "manual"


# ========== 缁熶竴鍝嶅簲妯″瀷 ==========

class ApiResponse(BaseModel):
    """缁熶竴鍝嶅簲妯″瀷"""
    code: int = 0
    message: str = "success"
    data: Any = None


# ========== 鍚屾浠诲姟鐩稿叧妯″瀷 ==========

class SyncTaskCreate(BaseModel):
    """鍒涘缓鍚屾浠诲姟璇锋眰妯″瀷"""
    name: str = Field(..., description="浠诲姟鍚嶇О")
    source_type: str = Field(..., description="鏉ユ簮绫诲瀷锛歴wagger/postman/yapi")
    source_url: Optional[str] = Field(None, description="鏉ユ簮URL")
    source_version: Optional[str] = Field(None, description="鏉ユ簮鐗堟湰")


class SyncTaskResponse(BaseModel):
    """鍚屾浠诲姟鍝嶅簲妯″瀷"""
    id: int
    project_id: int
    name: str
    source_type: str
    source_url: Optional[str]
    source_version: Optional[str]
    task_id: Optional[str]
    status: str
    progress: int
    total_count: int
    added_count: int
    updated_count: int
    deleted_count: int
    conflict_count: int
    error_message: Optional[str]
    execution_log: Optional[List[Dict[str, Any]]]
    started_at: Optional[str]
    completed_at: Optional[str]
    created_at: str
    created_by: Optional[int]

    model_config = ConfigDict(from_attributes=True)


# ========== 搴旂敤鍙樻洿鐩稿叧妯″瀷 ==========

class ChangeOperation(BaseModel):
    """鍙樻洿鎿嶄綔妯″瀷"""
    type: str = Field(..., description="鎿嶄綔绫诲瀷: add/update/deprecate/ignore")
    method: str = Field(..., description="HTTP 鏂规硶")
    path: str = Field(..., description="鎺ュ彛璺緞")
    strategy: Optional[str] = Field(None, description="鏇存柊绛栫暐: overwrite/merge (浠?update 绫诲瀷闇€瑕?")


class ApplyChangesRequest(BaseModel):
    """搴旂敤鍙樻洿璇锋眰妯″瀷"""
    operations: List[ChangeOperation] = Field(..., description="鍙樻洿鎿嶄綔鍒楄〃")


class ApplyChangesResponse(BaseModel):
    """搴旂敤鍙樻洿鍝嶅簲妯″瀷"""
    applied_count: int = Field(..., description="鎴愬姛搴旂敤鐨勫彉鏇存暟閲?)
    ignored_count: int = Field(..., description="蹇界暐鐨勫彉鏇存暟閲?)
    added_count: int = Field(..., description="鏂板鐨勬帴鍙ｆ暟閲?)
    updated_count: int = Field(..., description="鏇存柊鐨勬帴鍙ｆ暟閲?)
    deprecated_count: int = Field(..., description="搴熷純鐨勬帴鍙ｆ暟閲?)
    errors: List[str] = Field(default_factory=list, description="閿欒淇℃伅鍒楄〃")


# ========== 鍚屾浠诲姟 CRUD 鎺ュ彛 ==========

@router.post("/sync-tasks", response_model=ApiResponse)
async def create_sync_task(
    request: SyncTaskCreate,
    project_id: Optional[int] = Query(None, description="椤圭洰ID锛堝彲閫夛紝鏈彁渚涘垯浣跨敤鐢ㄦ埛涓婁笅鏂囷級"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    鍒涘缓鍚屾浠诲姟

    - **name**: 浠诲姟鍚嶇О
    - **source_type**: 鏉ユ簮绫诲瀷锛坰wagger/postman/yapi锛?
    - **source_url**: 鏉ユ簮URL
    - **source_version**: 鏉ユ簮鐗堟湰
    """
    trace_id = get_trace_id()

    # 鑾峰彇椤圭洰ID
    if project_id is None:
        project_id = get_current_project_id(db, current_user)

    logger.info(f"[{trace_id}] 鍒涘缓鍚屾浠诲姟: name={request.name}, source_type={request.source_type}, user={current_user.username}")

    # 鍒涘缓鍚屾浠诲姟
    sync_task = SyncTask(
        project_id=project_id,
        name=request.name,
        source_type=request.source_type,
        source_url=request.source_url,
        source_version=request.source_version,
        status=SyncTaskStatus.PENDING,
        total_count=0,
        added_count=0,
        updated_count=0,
        deleted_count=0,
        conflict_count=0,
        progress=0,
        created_by=current_user.id
    )

    db.add(sync_task)
    db.commit()
    db.refresh(sync_task)

    # 鍚姩寮傛鍚屾浠诲姟
    from app.celery.tasks import execute_sync_task
    celery_task = execute_sync_task.apply_async(args=[sync_task.id])

    # 鏇存柊 Celery 浠诲姟 ID
    sync_task.task_id = celery_task.id
    db.commit()

    logger.info(f"[{trace_id}] 鍚屾浠诲姟鍒涘缓骞跺惎鍔ㄦ垚鍔? id={sync_task.id}, celery_task_id={celery_task.id}")

    return ApiResponse(
        code=0,
        message="鍚屾浠诲姟宸插垱寤哄苟鍚姩",
        data={"id": sync_task.id, "task_id": celery_task.id}
    )


@router.get("/sync-tasks", response_model=ApiResponse)
async def get_sync_tasks(
    skip: int = Query(0, ge=0, description="璺宠繃璁板綍鏁?),
    limit: int = Query(50, ge=1, le=200, description="姣忛〉璁板綍鏁?),
    status: Optional[str] = Query(None, description="鐘舵€佽繃婊?),
    source_type: Optional[str] = Query(None, description="鏉ユ簮绫诲瀷杩囨护"),
    project_id: Optional[int] = Query(None, description="椤圭洰ID杩囨护"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    鑾峰彇鍚屾浠诲姟鍒楄〃

    - **skip**: 璺宠繃璁板綍鏁帮紙鍒嗛〉锛?
    - **limit**: 姣忛〉璁板綍鏁帮紙鏈€澶?00锛?
    - **status**: 鐘舵€佽繃婊?
    - **source_type**: 鏉ユ簮绫诲瀷杩囨护
    - **project_id**: 椤圭洰ID杩囨护锛堝彲閫夛紝鏈彁渚涘垯浣跨敤鐢ㄦ埛涓婁笅鏂囷級
    """
    trace_id = get_trace_id()

    # 鑾峰彇椤圭洰ID
    if project_id is None:
        project_id = get_current_project_id(db, current_user)

    logger.info(f"[{trace_id}] 鏌ヨ鍚屾浠诲姟鍒楄〃: skip={skip}, limit={limit}, user={current_user.username}, project_id={project_id}")

    # 鏋勫缓鏌ヨ
    query = db.query(SyncTask).filter(SyncTask.project_id == project_id)

    # 鐘舵€佽繃婊?
    if status:
        query = query.filter(SyncTask.status == status)

    # 鏉ユ簮绫诲瀷杩囨护
    if source_type:
        query = query.filter(SyncTask.source_type == source_type)

    # 鍒嗛〉
    total = query.count()
    tasks = query.order_by(SyncTask.created_at.desc()).offset(skip).limit(limit).all()

    # 杞崲涓哄搷搴旀ā鍨?
    result_list = []
    for task in tasks:
        result_list.append({
            "id": task.id,
            "project_id": task.project_id,
            "name": task.name,
            "source_type": task.source_type,
            "source_url": task.source_url,
            "source_version": task.source_version,
            "task_id": task.task_id,
            "status": task.status,
            "progress": task.progress,
            "total_count": task.total_count,
            "added_count": task.added_count,
            "updated_count": task.updated_count,
            "deleted_count": task.deleted_count,
            "conflict_count": task.conflict_count,
            "error_message": task.error_message,
            "execution_log": task.execution_log,
            "diff_data": task.diff_data,  # 娣诲姞鍙樻洿鏁版嵁
            "impact_analysis": task.impact_analysis,  # 娣诲姞褰卞搷鍒嗘瀽
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "created_at": task.created_at.isoformat() if task.created_at else "",
            "created_by": task.created_by
        })

    return ApiResponse(
        code=0,
        message="鏌ヨ鎴愬姛",
        data={
            "total": total,
            "items": result_list
        }
    )


@router.get("/sync-tasks/{task_id}", response_model=ApiResponse)
async def get_sync_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    鑾峰彇鍚屾浠诲姟璇︽儏

    - **task_id**: 浠诲姟ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 鏌ヨ鍚屾浠诲姟璇︽儏: id={task_id}, user={current_user.username}")

    task = db.query(SyncTask).filter(SyncTask.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"鍚屾浠诲姟涓嶅瓨鍦細{task_id}"
        )

    # IDOR 闃插尽锛氭鏌ヨ祫婧愬綊灞?
    if task.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鏃犳潈璁块棶璇ヨ祫婧?
        )

    result = {
        "id": task.id,
        "project_id": task.project_id,
        "name": task.name,
        "source_type": task.source_type,
        "source_url": task.source_url,
        "source_version": task.source_version,
        "task_id": task.task_id,
        "status": task.status,
        "progress": task.progress,
        "total_count": task.total_count,
        "added_count": task.added_count,
        "updated_count": task.updated_count,
        "deleted_count": task.deleted_count,
        "conflict_count": task.conflict_count,
        "error_message": task.error_message,
        "execution_log": task.execution_log,
        "diff_data": task.diff_data,  # 娣诲姞鍙樻洿鏁版嵁
        "impact_analysis": task.impact_analysis,  # 娣诲姞褰卞搷鍒嗘瀽
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else "",
        "created_by": task.created_by
    }

    return ApiResponse(
        code=0,
        message="鏌ヨ鎴愬姛",
        data=result
    )


@router.delete("/sync-tasks/{task_id}", response_model=ApiResponse)
async def delete_sync_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    鍒犻櫎鍚屾浠诲姟

    - **task_id**: 浠诲姟ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 鍒犻櫎鍚屾浠诲姟: id={task_id}, user={current_user.username}")

    task = db.query(SyncTask).filter(SyncTask.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"鍚屾浠诲姟涓嶅瓨鍦細{task_id}"
        )

    # IDOR 闃插尽锛氭鏌ヨ祫婧愬綊灞?
    if task.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鏃犳潈鍒犻櫎璇ヨ祫婧?
        )

    # 鍙兘鍒犻櫎宸插畬鎴愭垨澶辫触鐨勪换鍔?
    if task.status in [SyncTaskStatus.PENDING, SyncTaskStatus.RUNNING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="鏃犳硶鍒犻櫎杩涜涓殑浠诲姟"
        )

    db.delete(task)
    db.commit()

    logger.info(f"[{trace_id}] 鍚屾浠诲姟鍒犻櫎鎴愬姛: id={task_id}")

    return ApiResponse(
        code=0,
        message="鍒犻櫎鎴愬姛"
    )


@router.post("/sync-tasks/{task_id}/cancel", response_model=ApiResponse)
async def cancel_sync_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    鍙栨秷鍚屾浠诲姟

    - **task_id**: 浠诲姟ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 鍙栨秷鍚屾浠诲姟: id={task_id}, user={current_user.username}")

    task = db.query(SyncTask).filter(SyncTask.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"鍚屾浠诲姟涓嶅瓨鍦細{task_id}"
        )

    # IDOR 闃插尽锛氭鏌ヨ祫婧愬綊灞?
    if task.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鏃犳潈鎿嶄綔璇ヤ换鍔?
        )

    # 鍙兘鍙栨秷寰呭鐞嗘垨杩愯涓殑浠诲姟
    if task.status not in [SyncTaskStatus.PENDING, SyncTaskStatus.RUNNING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="鍙兘鍙栨秷寰呭鐞嗘垨杩愯涓殑浠诲姟"
        )

    task.status = SyncTaskStatus.CANCELLED
    db.commit()

    logger.info(f"[{trace_id}] 鍚屾浠诲姟鍙栨秷鎴愬姛: id={task_id}")

    return ApiResponse(
        code=0,
        message="浠诲姟宸插彇娑?
    )


# ========== 搴旂敤鍙樻洿鎺ュ彛 ==========

def _apply_changes_impl(
    db: Session,
    sync_task: SyncTask,
    operations: List[ChangeOperation],
    trace_id: str
) -> ApplyChangesResponse:
    """
    搴旂敤鍙樻洿鐨勬牳蹇冨疄鐜?

    Args:
        db: 鏁版嵁搴撲細璇?
        sync_task: 鍚屾浠诲姟
        operations: 鍙樻洿鎿嶄綔鍒楄〃
        trace_id: 杩借釜 ID

    Returns:
        ApplyChangesResponse: 搴旂敤缁撴灉
    """
    from app.platform.db.base import ApiDefinition, ApiEndpointGroup

    result = ApplyChangesResponse(
        applied_count=0,
        ignored_count=0,
        added_count=0,
        updated_count=0,
        deprecated_count=0,
        errors=[]
    )

    diff_data = sync_task.diff_data or {}

    # 鏋勫缓鍙樻洿鏄犲皠锛屾柟渚挎煡鎵?
    added_map = {(item['method'], item['path']): item for item in diff_data.get('added', [])}
    changed_map = {(item['method'], item['path']): item for item in diff_data.get('changed', [])}
    removed_map = {(item['method'], item['path']): item for item in diff_data.get('removed', [])}

    # 鑷姩鍒涘缓鍒嗙粍锛堝弬鑰冩帴鍙ｉ泦鎴愮殑閫昏緫锛?
    groups_map = {}  # group_name -> group_id
    all_groups = set()
    
    # 鏀堕泦鎵€鏈夐渶瑕佸垱寤虹殑鍒嗙粍
    for endpoint_data in diff_data.get('added', []):
        group_name = endpoint_data.get('group_name')
        if group_name:
            all_groups.add(group_name)
    
    for endpoint_data in diff_data.get('changed', []):
        group_name = endpoint_data.get('group_name')
        if group_name:
            all_groups.add(group_name)

    # 鍒涘缓鎴栨煡鎵惧垎缁?
    for group_name in all_groups:
        # 妫€鏌ュ垎缁勬槸鍚﹀凡瀛樺湪
        existing_group = db.query(ApiEndpointGroup).filter(
            ApiEndpointGroup.project_id == sync_task.project_id,
            ApiEndpointGroup.name == group_name
        ).first()

        if existing_group:
            groups_map[group_name] = existing_group.id
            logger.info(f"[{trace_id}] 浣跨敤宸插瓨鍦ㄧ殑鍒嗙粍: {group_name} (id={existing_group.id})")
        else:
            # 鍒涘缓鏂板垎缁?
            new_group = ApiEndpointGroup(
                project_id=sync_task.project_id,
                name=group_name,
                description=f"{group_name}鍒嗙粍",
                sort_order=len(groups_map)  # 鎸夐『搴忔帓搴?
            )
            db.add(new_group)
            db.flush()  # 鑾峰彇 group.id
            groups_map[group_name] = new_group.id
            logger.info(f"[{trace_id}] 鍒涘缓鏂板垎缁? {group_name} (id={new_group.id})")

    try:
        for op in operations:
            key = (op.method, op.path)

            if op.type == 'add':
                # 鏂板鎺ュ彛
                if key not in added_map:
                    result.errors.append(f"鏈壘鍒版柊澧炵殑鎺ュ彛: {op.method} {op.path}")
                    continue

                endpoint_data = added_map[key]

                # 妫€鏌ユ帴鍙ｆ槸鍚﹀凡瀛樺湪锛堥伩鍏嶉噸澶嶆彃鍏ワ級
                existing = db.query(ApiDefinition).filter(
                    ApiDefinition.project_id == sync_task.project_id,
                    ApiDefinition.method == op.method.upper(),
                    ApiDefinition.path == op.path
                ).first()

                if existing:
                    logger.warning(f"[{trace_id}] 鎺ュ彛宸插瓨鍦紝璺宠繃鏂板: {op.method} {op.path}")
                    result.errors.append(f"鎺ュ彛宸插瓨鍦? {op.method} {op.path}")
                    continue

                # 鑾峰彇鍒嗙粍 ID
                group_name = endpoint_data.get('group_name')
                group_id = groups_map.get(group_name) if group_name else None

                # 淇濆瓨鍘熷鐨?schema 缁撴瀯锛堜笉瑕佸悎骞?parameters锛?
                request_schema = endpoint_data.get('request_schema', {})
                response_schema = endpoint_data.get('response_schema', {})

                # 鍒涘缓鏂扮殑鎺ュ彛瀹氫箟
                new_endpoint = ApiDefinition(
                    project_id=sync_task.project_id,
                    method=op.method.upper(),
                    path=op.path,
                    group_id=group_id,
                    summary=endpoint_data.get('summary', '')[:200],  # 闄愬埗闀垮害
                    description=endpoint_data.get('summary', '')[:200],  # 闄愬埗闀垮害
                    request_schema=request_schema,
                                    response_schema=response_schema,
                                    tags=endpoint_data.get('tags', []),
                                    source_type=sync_task.source_type,
                                    source_url=sync_task.source_url,
                                    source_version=sync_task.source_version,
                                    status="active",
                                    schema_snapshot=endpoint_data  # 淇濆瓨瀹屾暣鐨勬帴鍙ｅ畾涔夊揩鐓?
                                )
                db.add(new_endpoint)
                db.flush()  # 鍒锋柊浠ヨ幏鍙?ID
                result.added_count += 1
                result.applied_count += 1
                logger.info(f"[{trace_id}] 鏂板鎺ュ彛: {op.method} {op.path}, group={group_name}")

                # 鑷姩鍒涘缓鐗堟湰蹇収锛堝湪鏂板鍚庯級
                try:
                    from app.api.v1.version_snapshots import auto_create_snapshot
                    snapshot = auto_create_snapshot(
                        db=db,
                        definition=new_endpoint,
                        trace_id=trace_id,
                        created_by=sync_task.created_by,
                        version_id=sync_task.version_id,
                        version_tag=endpoint_data.get('version_tag')
                    )
                    if snapshot:
                        logger.info(f"[{trace_id}] 鑷姩鍒涘缓鐗堟湰蹇収鎴愬姛: snapshot_id={snapshot.id}")
                except Exception as snapshot_error:
                    # 蹇収鍒涘缓澶辫触涓嶅奖鍝嶄富娴佺▼锛屼粎璁板綍鏃ュ織
                    logger.warning(f"[{trace_id}] 鑷姩鍒涘缓鐗堟湰蹇収澶辫触锛堜笉褰卞搷涓绘祦绋嬶級: {str(snapshot_error)}")

            elif op.type == 'update':
                # 鏇存柊鎺ュ彛
                if key not in changed_map:
                    result.errors.append(f"鏈壘鍒板彉鏇寸殑鎺ュ彛: {op.method} {op.path}")
                    continue

                endpoint_data = changed_map[key]

                # 鏌ユ壘鐜版湁鐨勬帴鍙ｅ畾涔?
                existing_endpoint = db.query(ApiDefinition).filter(
                    ApiDefinition.project_id == sync_task.project_id,
                    ApiDefinition.method == op.method.upper(),
                    ApiDefinition.path == op.path
                ).first()

                if not existing_endpoint:
                    result.errors.append(f"鎺ュ彛涓嶅瓨鍦紝鏃犳硶鏇存柊: {op.method} {op.path}")
                    continue

# 鑾峰彇鍒嗙粍 ID
                group_name = endpoint_data.get('group_name')
                group_id = groups_map.get(group_name) if group_name else None

                # 淇濆瓨鍘熷鐨?schema 缁撴瀯锛堜笉瑕佸悎骞?parameters锛?
                request_schema = endpoint_data.get('request_schema', {})
                response_schema = endpoint_data.get('response_schema', {})

                if strategy == 'overwrite':
                    # 瑕嗙洊妯″紡锛氬畬鍏ㄦ浛鎹?Schema
                    existing_endpoint.request_schema = request_schema
                    existing_endpoint.response_schema = response_schema
                    existing_endpoint.summary = endpoint_data.get('summary', existing_endpoint.summary)[:200]  # 闄愬埗闀垮害
                    existing_endpoint.description = endpoint_data.get('summary', existing_endpoint.description)[:200]  # 闄愬埗闀垮害
                    existing_endpoint.schema_snapshot = endpoint_data  # 鏇存柊蹇収
                    
                    # 鏇存柊鍒嗙粍
                    group_name = endpoint_data.get('group_name')
                    if group_name and group_name in groups_map:
                        existing_endpoint.group_id = groups_map[group_name]
                        
                elif strategy == 'merge':
                    # 鍚堝苟妯″紡锛氬悎骞?Schema锛堜繚鐣欑幇鏈夐厤缃級
                    # TODO: 瀹炵幇鏇存櫤鑳界殑鍚堝苟閫昏緫
                    existing_endpoint.request_schema = request_schema
                    existing_endpoint.response_schema = response_schema
                    existing_endpoint.schema_snapshot = endpoint_data  # 鏇存柊蹇収
                    
                    # 鏇存柊鍒嗙粍
                    group_name = endpoint_data.get('group_name')
                    if group_name and group_name in groups_map:
                        existing_endpoint.group_id = groups_map[group_name]

                existing_endpoint.updated_at = datetime.utcnow()
                result.updated_count += 1
                result.applied_count += 1
                logger.info(f"[{trace_id}] 鏇存柊鎺ュ彛: {op.method} {op.path} (绛栫暐: {strategy})")

                # 鑷姩鍒涘缓鐗堟湰蹇収锛堝湪鏇存柊鍚庯級
                try:
                    from app.api.v1.version_snapshots import auto_create_snapshot
                    snapshot = auto_create_snapshot(
                        db=db,
                        definition=existing_endpoint,
                        trace_id=trace_id,
                        created_by=sync_task.created_by,
                        version_id=sync_task.version_id,
                        version_tag=endpoint_data.get('version_tag')
                    )
                    if snapshot:
                        logger.info(f"[{trace_id}] 鑷姩鍒涘缓鐗堟湰蹇収鎴愬姛: snapshot_id={snapshot.id}")
                except Exception as snapshot_error:
                    # 蹇収鍒涘缓澶辫触涓嶅奖鍝嶄富娴佺▼锛屼粎璁板綍鏃ュ織
                    logger.warning(f"[{trace_id}] 鑷姩鍒涘缓鐗堟湰蹇収澶辫触锛堜笉褰卞搷涓绘祦绋嬶級: {str(snapshot_error)}")

            elif op.type == 'deprecate':
                # 搴熷純鎺ュ彛
                if key not in removed_map:
                    result.errors.append(f"鏈壘鍒板垹闄ょ殑鎺ュ彛: {op.method} {op.path}")
                    continue

                # 鏌ユ壘鐜版湁鐨勬帴鍙ｅ畾涔?
                existing_endpoint = db.query(ApiDefinition).filter(
                    ApiDefinition.project_id == sync_task.project_id,
                    ApiDefinition.method == op.method.upper(),
                    ApiDefinition.path == op.path
                ).first()

                if not existing_endpoint:
                    result.errors.append(f"鎺ュ彛涓嶅瓨鍦紝鏃犳硶搴熷純: {op.method} {op.path}")
                    continue

                # 鏍囪涓哄簾寮冿紙杞垹闄わ級
                existing_endpoint.status = "archived"
                result.deprecated_count += 1
                result.applied_count += 1
                logger.info(f"[{trace_id}] 搴熷純鎺ュ彛: {op.method} {op.path}")

            elif op.type == 'ignore':
                # 蹇界暐鍙樻洿
                result.ignored_count += 1
                logger.info(f"[{trace_id}] 蹇界暐鍙樻洿: {op.method} {op.path}")

        # 鎻愪氦浜嬪姟
        db.commit()

        logger.info(f"[{trace_id}] 鍙樻洿搴旂敤瀹屾垚: {result.applied_count} 涓彉鏇村凡搴旂敤, 鍒涘缓浜?{len(groups_map)} 涓垎缁?)

    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 搴旂敤鍙樻洿鏃跺彂鐢熼敊璇? {str(e)}")
        result.errors.append(f"搴旂敤鍙樻洿澶辫触: {str(e)}")
        raise

    return result


def _sync_knowledge_graph_from_openapi(db: Session, project_id: int, diff_data: dict) -> None:
    """Build or update graph nodes based on API sync diff data."""
    from app.platform.db.base import ApiDefinition
    from app.domains.knowledge_graph.graph_service import KnowledgeGraphService

    candidates = []
    for item in diff_data.get("added", []) + diff_data.get("changed", []):
        method = item.get("method")
        path = item.get("path")
        if not method or not path:
            continue
        definition = db.query(ApiDefinition).filter(
            ApiDefinition.project_id == project_id,
            ApiDefinition.method == method.upper(),
            ApiDefinition.path == path
        ).first()
        if not definition:
            continue

        candidates.append({
            "id": definition.id,
            "method": definition.method,
            "path": definition.path,
            "summary": definition.summary,
            "tags": definition.tags or [],
        })

    if not candidates:
        return

    service = KnowledgeGraphService(db)
    service.build_from_openapi(candidates)


@router.post("/sync-tasks/{task_id}/apply", response_model=ApiResponse)
async def apply_changes(
    task_id: int,
    request: ApplyChangesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    搴旂敤鍚屾浠诲姟鐨勫彉鏇?

    - **task_id**: 鍚屾浠诲姟ID
    - **operations**: 鍙樻洿鎿嶄綔鍒楄〃
        - type: 鎿嶄綔绫诲瀷 (add/update/deprecate/ignore)
        - method: HTTP 鏂规硶
        - path: 鎺ュ彛璺緞
        - strategy: 鏇存柊绛栫暐 (overwrite/merge锛屼粎 update 闇€瑕?
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 搴旂敤鍙樻洿: task_id={task_id}, user={current_user.username}")

    # 妫€鏌ュ悓姝ヤ换鍔℃槸鍚﹀瓨鍦?
    task = db.query(SyncTask).filter(SyncTask.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"鍚屾浠诲姟涓嶅瓨鍦細{task_id}"
        )

    # IDOR 闃插尽锛氭鏌ヨ祫婧愬綊灞?
    if task.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鏃犳潈鎿嶄綔璇ヤ换鍔?
        )

    # 妫€鏌ヤ换鍔＄姸鎬?
    if task.status != SyncTaskStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="鍙兘搴旂敤宸插畬鎴愮殑鍚屾浠诲姟"
        )

    # 妫€鏌ユ槸鍚︽湁鍙樻洿鏁版嵁
    if not task.diff_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="璇ヤ换鍔℃病鏈夊彉鏇存暟鎹?
        )

    try:
        # 搴旂敤鍙樻洿
        result = _apply_changes_impl(db, task, request.operations, trace_id)

        try:
            _sync_knowledge_graph_from_openapi(db, task.project_id, task.diff_data or {})
        except Exception as graph_error:
            logger.warning(f"[{trace_id}] Graph 鍚屾澶辫触锛堜笉褰卞搷涓绘祦绋嬶級: {graph_error}")

        logger.info(f"[{trace_id}] 鍙樻洿搴旂敤鎴愬姛: {result.applied_count} 涓彉鏇?)

        return ApiResponse(
            code=0,
            message="鍙樻洿搴旂敤鎴愬姛",
            data=result.model_dump()
        )

    except Exception as e:
        logger.error(f"[{trace_id}] 搴旂敤鍙樻洿澶辫触: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搴旂敤鍙樻洿澶辫触锛歿str(e)}"
        )

