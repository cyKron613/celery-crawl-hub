from fastapi import status
from src.main.repository.algorithm import (
    AlgorithmTagRepository, TestRepository
)
from src.main.schema.algorithm import (
    AlgorithmTagResponseVo,
)
from src.main.core.orm.service.base import BaseService
from fastapi import status
from loguru import logger

class TestService:
    async def test(self) -> dict:
        try:
            """测试服务层"""
            from datetime import datetime
            return {"code": status.HTTP_200_OK, "message": "测试服务层成功", "data": {"time": f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}}
        except Exception as e:
            logger.error(f"测试服务层时出错: {e}")
            return {"code": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": "测试服务层失败", "detail": f"测试服务层失败: {str(e)}"}


class TestDbService(BaseService[TestRepository]):
    async def test_db(self) -> AlgorithmTagResponseVo:
        """测试数据库连接"""
        tags = await self.repo.test_db()
        return AlgorithmTagResponseVo(code=status.HTTP_200_OK, message="标签获取成功", data=tags)

class AlgorithmTagService(BaseService[AlgorithmTagRepository]):
    async def get_algorithm_tag_by_name(self, tag_type_name: str) -> AlgorithmTagResponseVo:
        try:
            """根据tag_type_name获取算法标签"""
            tag = await self.repo.get_tag_by_name(tag_type_name)
            if not tag:
                return AlgorithmTagResponseVo(code=status.HTTP_404_NOT_FOUND, message=f"一级标签：{tag_type_name} 不存在")
            return AlgorithmTagResponseVo(code=status.HTTP_200_OK, message="标签获取成功", data=tag)
        except Exception as e:
            logger.error(f"获取算法标签时出错: {e}")
            return AlgorithmTagResponseVo(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="获取标签失败",
                detail=f"获取算法标签失败: {str(e)}"
            )