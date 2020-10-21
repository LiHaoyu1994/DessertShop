import pandas as pd
import numpy as np
import xlwt
import time

goods_dict = {}
encoding = 'utf-8'


# 从csv读取数据,返回一个columns为["user_id","goods_name","goods_num","goods_date","weekday"]的数据框
def get_isbn_from_csv(file_name: str) -> pd.DataFrame:
    global goods_dict, encoding
    dataFrame, dataFrame2 = pd.DataFrame(), []
    try:
        dataFrame = pd.read_csv(file_name, encoding='utf-8', dtype=str)
    except UnicodeDecodeError:
        dataFrame = pd.read_csv(file_name, encoding='gbk', dtype=str)
        encoding = 'gbk'
    # 保留指定的列
    dataFrame = dataFrame[["收件人/提货人姓名", "下单账号", "商品ID", "商品名称", "商品件数"]]
    # 显示所有列
    pd.set_option('display.max_columns', None)
    for i in range(len(dataFrame)):
        # 合并用户姓名与手机号,生成用户名ID以替换这两部分信息
        user_id = dataFrame.loc[i, "收件人/提货人姓名"] + "+" + dataFrame.loc[i, "下单账号"]
        # 扫描"商品ID" 与"商品名称"列,更新goods_dict
        goods_num, goods_info = goods_id_format(dataFrame.loc[i, "商品ID"]), goods_name_format(dataFrame.loc[i, "商品名称"])
        for j in range(len(goods_num)):
            # 更新goods_dict
            goods_dict[goods_num[j]] = goods_info[j]["name"]
            # 添加到dataFrame2
            dataFrame2.append(
                {"user_id": user_id, "goods_name": goods_info[j]["name"], "goods_num": goods_info[j]["num"]})
            if "date" in goods_info[j]:
                dataFrame2[-1]["date"] = goods_info[j]["date"]
            if "weekday" in goods_info[j]:
                dataFrame2[-1]["weekday"] = goods_info[j]["weekday"]
    return pd.DataFrame(dataFrame2)


# 对新生成的数据框二次处理,根据日期进行排序并合并其全部订单,直接写入xls文件
def consolidated_orders(dataFrame: pd.DataFrame, output_file_name: str) -> None:
    global encoding
    # 对于dataFrame给来的数据,先根据date排序,整理出不同date下的goods_name有哪些,以生成全部列名
    date_goods_name, goods_ids, user_ids = {}, [], []
    for i in range(len(dataFrame)):
        # 把商品-日期id加入date_goods,去重.以方便生成columns
        if dataFrame.loc[i, "date"] not in date_goods_name:
            date_goods_name[dataFrame.loc[i, "date"]] = set()
        date_goods_name[dataFrame.loc[i, "date"]].add(dataFrame.loc[i, "goods_name"])
        # 把user_id 放入user_ids,去重.最后生成行表
        if dataFrame.loc[i, "user_id"] not in user_ids:
            user_ids.append(dataFrame.loc[i, "user_id"])

    # 生成日期+商品名的列表,以统计所有列
    for date in date_goods_name:
        for goods_name in date_goods_name[date]:
            goods_ids.append(str(date) + "+" + goods_name)
    goods_ids.sort()
    # 把顺丰和达达移到最前面
    for i, goods_id in enumerate(goods_ids):
        if "顺丰" in goods_id or "达达" in goods_id:
            goods_ids.insert(0, goods_ids[i])
            del goods_ids[i + 1]

    # 初始化数据框以固定列名
    result = []
    for user_id in user_ids:
        data = {"user_id": user_id}
        for goods_id in goods_ids:
            data[goods_id] = 0
        result.append(data)

    # 遍历原始表格,在result里面对应改动
    for i in range(len(dataFrame)):
        user_id = dataFrame.loc[i, "user_id"]
        goods_id = str(dataFrame.loc[i, "date"]) + "+" + dataFrame.loc[i, "goods_name"]
        # 在result列表中迅速定位user_id
        for j in range(len(result)):
            if result[j]["user_id"] == user_id:
                result[j][goods_id] += 1
    result = pd.DataFrame(result)

    # 使用xlwt写入excel文件,设置行宽与自动换行
    style = xlwt.XFStyle()
    style.alignment.wrap = 1  # 设置自动换行
    workbook = xlwt.Workbook(encoding=encoding)  # 设置编码格式
    worksheet = workbook.add_sheet("日期导出 {}".format(time.strftime("%Y-%m-%d")))  # 设置表单名称
    # 改变列宽
    worksheet.col(0).width = 256 * 25
    for i in range(len(goods_ids)):
        worksheet.col(i + 1).width = 256 * 15
    # 先把列名写入文件
    worksheet.write(0, 0, "user_id", style)
    for index, value in enumerate(goods_ids):
        worksheet.write(0, index + 1, value, style)
    # 再把result内容写入文件
    for i in range(len(result)):
        for key, value in enumerate(result.iloc[[i]]):
            if key == 0:
                worksheet.write(i + 1, key, str(result.iloc[i, key]), style)
            elif int(result.iloc[i, key]) > 0:
                worksheet.write(i + 1, key, int(result.iloc[i, key]), style)
    workbook.save(output_file_name)


# 从单一的商品名称剥离成list-dict形式
def goods_name_format(goods_name: str) -> list:
    result = []
    for words in goods_name.split(";"):
        data = {}
        # 正常商品处理(字样:"9/24 周四烘焙：农夫核桃卷(1)")
        if '0' <= words[0] <= '9':
            # 剥离日期信息
            data["date"] = words[:words.find(" ")].strip()
            # 剥离weekday信息,切割周几的信息大部分存在"："形式依此分割
            if "周" in words:
                data["weekday"] = words[words.find("周"):words.find("周") + 2]
            # 剥离商品名称信息,通过"烘焙"/"制作"/"预定"后面的字样分割
            if "烘焙" in words:
                data["name"] = words[words.find("烘焙") + 3:words.rfind("(")].strip()
            elif "制作" in words:
                data["name"] = words[words.find("制作") + 3:words.rfind("(")].strip()
            # 剥离购买份数信息
            data["num"] = words[words.rfind("(") + 1:words.rfind(")")].strip()
        # 顺丰快递/达达配送的处理(字样:"顺丰快递(当天件/次日达)(1)")
        elif words[:2] in ["顺丰", "达达"]:
            data["name"] = words[:words.rfind("(")].strip()
            data["num"] = words[words.rfind("(") + 1:words.rfind(")")].strip()
        # 一些没有日期的特殊款式(例:日式生巧（黑巧）预定：仅限自提和3KM以内的配送，请提前3天以上预定(9块简装)(1))
        else:
            data["name"] = words[:words.rfind("(")].strip()
            data["num"] = words[words.rfind("(") + 1:words.rfind(")")].strip()
        result.append(data)
    return result


# 商品ID剥离成list形式的ID
def goods_id_format(goods_id: str) -> list:
    return goods_id.split(";")


def data_reduction(input_file_name: str) -> None:
    df, output_file_name = get_isbn_from_csv(input_file_name), input_file_name[:-4] + "_软件生成.xls"
    consolidated_orders(df, output_file_name)


if __name__ == '__main__':
    # 导出csv中的数据
    # data_reduction("微店导出的原始数据.csv")
    data_reduction("C:\\Users\\Administrator\\Desktop\\202009272223.csv")
