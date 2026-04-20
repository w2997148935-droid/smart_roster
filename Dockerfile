# 强制使用 Python 3.11 官方镜像
FROM public.ecr.aws/render/cpython:3.11

# 设置工作目录
WORKDIR /opt/render/project/src

# 这里的命令会在构建阶段运行
# 我们显式地升级 pip 和 setuptools，确保环境纯净
RUN pip install --upgrade pip setuptools wheel

# 暴露端口
EXPOSE 10000
