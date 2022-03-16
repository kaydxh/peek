#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd


# In[2]:


df = pd.read_excel("./testdata/clothes.xlsx")


# In[3]:


from pyecharts import options as opts
from pyecharts.charts import Bar


# In[4]:


bar = (
        Bar()
        .add_xaxis(df["商品"].to_list())
        .add_yaxis("商家A", df["商家A"].tolist())
        .add_yaxis("商家B", df["商家B"].to_list())
        .set_global_opts(title_opts= opts.TitleOpts(title="商品销量对比图"))
        )
bar.render_notebook()


# In[ ]:




