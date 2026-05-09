import concurrent.futures
import os

from obs import ObsClient, PutObjectHeader, GetObjectHeader, DeleteObjectsRequest, Object
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


class HuaWeiObsClient:

    def __init__(self):
        """初始化"""
        self.obs_access_key = os.getenv("OBS_ACCESS_KEY")
        self.obs_secret_key = os.getenv("OBS_SECRET_KEY")
        self.obs_server = os.getenv("OBS_SERVER_URL")
        self.bucket_name = os.getenv("OBS_BUCKET_NAME")
        self.file_headers = PutObjectHeader()
        self.download_headers = GetObjectHeader()
        self.file_headers.contentType = 'text/plain'
        self.encoding_type = 'url'
        self.obs_client = ObsClient(access_key_id=self.obs_access_key,
                                    secret_access_key=self.obs_secret_key,
                                    server=self.obs_server)

    @staticmethod
    def _print_bucket_info(buckets):
        """打印桶信息"""
        logger.info(f'owner_id: {buckets.owner.owner_id}')
        index = 1
        for bucket in buckets.buckets:
            logger.info('bucket [' + str(index) + ']: ')
            logger.info(f'name: {bucket.name} | create_date: {bucket.create_date} | location:{bucket.location}')
            index += 1

    @staticmethod
    def _print_bucket_obj_info(obj):
        """打印桶内对象信息"""
        index = 1
        oss_path_list = {}
        for content in obj.contents:
            # logger.info('object [' + str(index) + ']: ')
            # logger.info(f'oss_path: {content.key} | lastModified: {content.lastModified} | etag: {content.etag}')
            # logger.info(f'file_size: {content.size} | storageClass: {content.storageClass}')
            # logger.info(f'owner_id: {content.owner.owner_id} | owner_name: {content.owner.owner_name}')
            # logger.info(f'-' * 100)
            # oss_path_list.append({content.key: content.lastModified})
            oss_path_list[content.key] = content.lastModified
            index += 1
        return oss_path_list

    @staticmethod
    def _handle_error(response):
        logger.error(
            f'List Buckets Failed | requestId: {response.requestId} | errorCode: {response.errorCode} | errorMessage: {response.errorMessage}')

    def has_files_in_folder(self, obs_folder_path: str) -> bool:
        """
        判断 OBS 文件夹内是否有文件
        :param obs_folder_path: OBS 文件夹路径（如 "graph_data_input/"）
        :return: 如果文件夹内有文件返回 True，否则返回 False
        """
        try:
            # 列出文件夹内容
            resp = self.obs_client.listObjects(self.bucket_name, prefix=obs_folder_path)
            if resp.status < 300:
                # 遍历 contents 列表
                for content in resp.body.contents:
                    # 忽略文件夹对象（以 / 结尾且 size 为 0）
                    if content.key.endswith('/') and content.size == 0:
                        continue
                    # 如果存在 size > 0 的对象，则文件夹内有文件
                    if content.size > 0:
                        return True
                # 如果没有 size > 0 的对象，则文件夹内没有文件
                return False
            else:
                logger.error(f"Failed to list objects in folder: {obs_folder_path}")
                return False
        except Exception as e:
            logger.error(f"Error checking folder files: {str(e)}")
            return False

    def list_buckets(self, is_query_location: str = False):
        """查看所有桶
        :param: is_query_location: is_query_location=False 是否同时查询桶的区域位置
        """
        try:
            resp = self.obs_client.listBuckets(isQueryLocation=is_query_location)
            if resp.status < 300:
                logger.info('List Buckets Succeeded')
                logger.info(f'requestId: {resp.requestId}')
                self._print_bucket_info(resp.body)
            else:
                self._handle_error(resp)
        except Exception as e:
            logger.error(f'List Buckets Failed: {str(e)}')
            raise

    def list_buckets_objects(self, prefix: str):
        """查看桶内对象
        :param prefix: 指定目录起始位置  prefix='test/'  tips: 注意尾部斜杠
        """
        try:
            resp = self.obs_client.listObjects(self.bucket_name, prefix=prefix, encoding_type=self.encoding_type)
            if resp.status < 300:
                # logger.info('List Objects Succeeded')
                # logger.info(f'requestId: {resp.requestId}')
                # self._print_bucket_obj_info(resp.body)
                oss_path_list = self._print_bucket_obj_info(resp.body)
                return oss_path_list
            else:
                self._handle_error(resp)
        except Exception as e:
            logger.error(f'List Objects Failed: {str(e)}')
            raise

    def upload_bucket_file(self, obs_file_path: str, local_file_path: str):
        """创建桶内文件
        :param obs_file_path: 上传后的文件名   obs_file_path='test/船舶运营.pdf'
        :param local_file_path: 本地上传路径   local_file_path='/home/ccy/test/船舶运营.pdf'
        """
        try:
            resp = self.obs_client.putFile(self.bucket_name, obs_file_path, local_file_path, self.file_headers)
            if resp.status < 300:
                logger.info(f'Create Object Succeeded, obs_file_path: {obs_file_path}')
                logger.info(f'requestId: {resp.requestId}')
            else:
                self._handle_error(resp)
        except Exception as e:
            logger.error(f'Create Object Failed: {str(e)}')
            raise

    def upload_multi_bucket_files(self, obs_file_prefix: str, local_file_path_list: list[str]):
        """ 多线程上传多个文件：上传的文件名与目标文件名将保持一致。
        :param obs_file_prefix: 批量文件上传的根路径   obs_file_prefix="test/"  tips: 注意尾部斜杠
        :param local_file_path_list: 需要上传的文件列表。都为绝对路径。  local_file_path_list=[...]
        """
        try:
            # 使用线程池来并发执行上传任务
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # 将每个文件的上传任务提交给线程池
                futures = [executor.submit(self.upload_bucket_file, obs_file_prefix + path.split('\\')[-1], path) for
                           path in local_file_path_list]
                # 等待所有上传任务完成
                for future in concurrent.futures.as_completed(futures):
                    future.result()  # 这将抛出异常，如果上传失败
        except Exception as e:
            logger.error(f'upload_multi_bucket_files error: {str(e)}')
            raise

    def adownload_bucket_file(self, obs_file_path: str, download_path: str):
        """下载文件
        :param obs_file_path:  obs（带路径）的文件名， 所需下载的文件
        :param download_path: 下载到本地的绝对路径
        """
        try:
            resp = self.obs_client.getObject(self.bucket_name, obs_file_path, download_path,
                                             headers=self.download_headers)

            if resp.status < 300:
                logger.info('Download Object Succeeded')
                logger.info(f'requestId: {resp.requestId}')
            else:
                self._handle_error(resp)
        except Exception as e:
            logger.error(f'Download Object Failed: {str(e)}')
            raise

    def download_folder(self, obs_folder_path: str, local_folder_path: str):
        """
        批量下载文件
        :param obs_folder_path: OBS 文件夹路径（如 "test/"）
        :param local_folder_path: 本地保存路径（如 "./downloads/"）
        """
        try:
            if not self.has_files_in_folder(obs_folder_path):
                logger.error(f"文件夹为空: {obs_folder_path}")
                return

            # 确保本地文件夹存在
            os.makedirs(local_folder_path, exist_ok=True)

            # 列出 OBS 文件夹中的所有文件
            resp = self.obs_client.listObjects(self.bucket_name, prefix=obs_folder_path)
            if resp.status < 300:
                for content in resp.body.contents:
                    if content.key.endswith('/') or content.size == 0:
                        continue
                        # 构造本地文件路径
                    relative_path = content.key[len(obs_folder_path):]  # 去除前缀
                    local_file_path = f"{local_folder_path}{relative_path}"


                    # 确保本地文件夹存在
                    os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

                    # 下载文件
                    logger.info(f"Downloading: {content.key} -> {local_file_path}")
                    self.obs_client.getObject(self.bucket_name, content.key, local_file_path)
            else:
                logger.error(f"Failed to list objects in folder: {obs_folder_path}")
        except Exception as e:
            logger.error(f"Download folder failed: {str(e)}")
            raise

    def delete_single_object(self, obs_file_path: str, version_id: str = "null"):
        """删除单一文件
        parameters:
        obs_file_path: obs（带路径）的文件名, 所需删除的文件
        download_path: 下载到本地的绝对路径
        """
        try:
            # 如果删除多版本对象请指定versionId,未开启多版本则为null
            resp = self.obs_client.deleteObject(self.bucket_name, obs_file_path, version_id)
            if resp.status < 300:
                logger.info('Delete Object Succeeded')
                logger.info(f'requestId: {resp.requestId}', )
                logger.info(f'deleteMarker: {resp.body.deleteMarker}')
                logger.info(f'versionId: {resp.body.versionId}')
            else:
                self._handle_error(resp)
        except Exception as e:
            logger.error(f'delete {obs_file_path} Object Failed: {str(e)}')
            raise

    def delete_multi_objects(self, object_list: list):
        """删除多个文件
        parameters:
        object_list: 待删除的文件列表
        """
        try:
            map_list = list(map(Object, object_list))
            resp = self.obs_client.deleteObjects(self.bucket_name,
                                                 DeleteObjectsRequest(
                                                     quiet=False,
                                                     objects=map_list,
                                                     encoding_type=self.encoding_type)
                                                 )
            if resp.status < 300:
                if resp.body.deleted:
                    index = 1
                    for delete in resp.body.deleted:
                        logger.info('delete[' + str(index) + ']')
                        logger.info('key: {}'.format(delete.key), ',deleteMarker: {}'.format(delete.deleteMarker),
                                    'deleteMarkerVersionId: {}'.format(delete.deleteMarkerVersionId))
                        logger.info('versionId: {}'.format(delete.versionId))
                        index += 1
                if resp.body.error:
                    index = 1
                    for err in resp.body.error:
                        logger.error('err[' + str(index) + ']')
                        logger.error('key:', err.key, ',code:', err.code, ',message:', err.message)
                        logger.error('versionId:', err.versionId)
                        index += 1
            else:
                self._handle_error(resp)
        except Exception as e:
            logger.error(f'Delete Objects Failed: {str(e)}')
            raise

    def check_file_exists(self, bucket_name: str, object_key: str) -> bool:
        """
        检查 OBS 中是否存在指定文件
        :param bucket_name: 桶名称
        :param object_key: 文件路径（如 "graph_data_input/AI算法开发工程师.md"）
        :return: 如果文件存在返回 True，否则返回 False
        """
        try:
            resp = self.obs_client.getObjectMetadata(bucket_name, object_key)
            return resp.status < 300
        except Exception as e:
            print(f"Error checking file existence: {str(e)}")
            return False

    def move_object(self, source_folder: str, target_folder: str, object_name: str):
        """
        将文件夹中的文件移动到另一个文件夹
        :param source_folder: 源文件夹路径（如 "folderA/"）
        :param target_folder: 目标文件夹路径（如 "folderB/"）
        :param object_name: 文件名（如 "fileA.pdf"）
        """
        try:
            # 构造源路径和目标路径
            source_path = f"{source_folder.rstrip('/')}/{object_name}"
            target_path = f"{target_folder.rstrip('/')}/{object_name}"
            print(source_path, target_path)

            # 复制文件到目标文件夹
            copy_resp = self.obs_client.copyObject(
                sourceBucketName=self.bucket_name,
                sourceObjectKey=source_path,
                destBucketName=self.bucket_name,
                destObjectKey=target_path
            )
            if copy_resp.status >= 300:
                self._handle_error(copy_resp)
                raise Exception(f"Failed to copy object: {source_path} to {target_path}")

            # 删除源文件
            delete_resp = self.obs_client.deleteObject(self.bucket_name, source_path)
            if delete_resp.status >= 300:
                self._handle_error(delete_resp)
                raise Exception(f"Failed to delete object: {source_path}")

            logger.info(f"Object moved successfully: {source_path} -> {target_path}")
        except Exception as e:
            logger.error(f"Failed to move object: {str(e)}")
            raise


# 使用示例
if __name__ == "__main__":
    obs_client = HuaWeiObsClient()
    # obs_client.upload_bucket_file(f"test/海科自研OCR接口文档.pdf",
    #                               r"C:\Users\cykro\Desktop\海科自研OCR接口文档.pdf")

    # for i in range(50):
    #     obs_client.upload_bucket_file(f"test/船舶运营{i}.pdf",
    #                                   r"C:\code\data_factory\static\data_example\160. 船舶运营.pdf")
    #
    # obs_client.upload_multi_bucket_files(obs_file_prefix="test/", local_file_path_list=[
    #     'C:\\code\\data_factory\\static\\test\\pymu_pdf_to_txt.py', 'C:\\code\\data_factory\\static\\test\\test.md',
    #     'C:\\code\\data_factory\\static\\test\\test.py', 'C:\\code\\data_factory\\static\\test\\航海学知识点.docx'])
    #
    # obs_client.download_folder(os.getenv("DATA_DIR"), os.getenv("OUTPUT_DIR"))
    #
    # ll = obs_client.list_buckets_objects(r"高质量数据集/Step1/")

    objects = obs_client.list_buckets_objects(r"crawl_data/images")  # 列出桶内所有文件
    extension = [".jpg"]
    total_list = [file_name for file_name, last_modified in objects.items() if file_name.endswith(tuple(extension))]

    # 获取所有文件夹名字列表
    # folder_list = list(set([file_name.split('/')[2] for file_name in total_list]))
    print(total_list)

    

    #
    # obs_client.delete_single_object("test/航海学知识点.docx")
    #
    # obs_client.delete_multi_objects([f"test/船舶运营{i}.pdf" for i in range(50)])
    # print(obs_client.check_file_exists("your-bucket", "path/to/file.md"))

    # 将 folderA 中的 fileA.pdf 移动到 folderB
    # obs_client.move_object(source_folder="graph_data_input/", target_folder="graph_data_done/", object_name="AI算法开发工程师.md")

    # 批量上传
    # from pathlib import Path
    #
    # output_dir = r"../test"
    # file_lists = list(Path(output_dir).rglob("*.md"))
    # for i in file_lists:
    #     print(i)
    #
    #     # 指定 OBS 根路径
    # obs_file_prefix = "test/"
    #
    # # 获取 test/ 目录下的所有文件路径
    # test_directory = "../test"  # 替换为实际的目录路径
    # local_file_path_list = [os.path.join(test_directory, f) for f in os.listdir(test_directory) if
    #                         os.path.isfile(os.path.join(test_directory, f))]
    #
    # # 上传文件
    # uploader.upload_multi_bucket_files(obs_file_prefix, local_file_path_list)
