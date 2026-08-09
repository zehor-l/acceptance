import io
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="3G RAN Site Acceptance & KPI Analyzer", layout="wide"
)

st.title("📶 3G RAN Site Acceptance & KPI Trend Analyzer")
st.markdown(
    "**Expert Rule:** Post-submission performance (15 days after) must be"
    " equal to or better than pre-submission performance (15 days before)."
)

# Sidebar File Uploaders
st.sidebar.header("1. Upload Data Files")
kpi_file = st.sidebar.file_uploader(
    "Upload 3G KPI Report (.xlsx)", type=["xlsx", "xls", "csv"]
)
sub_file = st.sidebar.file_uploader(
    "Upload Submission Dates (.xlsx)", type=["xlsx", "xls", "csv"]
)

if kpi_file is not None and sub_file is not None:
  # Load Data
  if kpi_file.name.endswith(".csv"):
    df_kpi = pd.read_csv(kpi_file)
  else:
    df_kpi = pd.read_excel(kpi_file)

  if sub_file.name.endswith(".csv"):
    df_sub = pd.read_csv(sub_file)
  else:
    df_sub = pd.read_excel(sub_file)

  # Clean column names
  df_sub.columns = [c.strip() for c in df_sub.columns]

  # Parse Dates
  df_kpi["Date"] = pd.to_datetime(df_kpi["Date"], errors="coerce")
  df_sub["Swap date"] = pd.to_datetime(df_sub["Swap date"], errors="coerce")


  # Helper to map site names between KPI file and Submission file
  def get_matched_site(nodeb_name):
    name_str = str(nodeb_name).upper()
    for s in df_sub["Site"].dropna():
      clean_s = str(s).upper().replace("O", "")
      if clean_s in name_str:
        return s
    return nodeb_name


  df_kpi["Matched_Site"] = df_kpi["NODEBNAME"].apply(get_matched_site)
  data = pd.merge(
      df_kpi,
      df_sub,
      left_on="Matched_Site",
      right_on="Site",
      how="inner",
      suffixes=("", "_sub"),
  )

  # Calculate Day Difference from Submission Date
  data["Days_Diff"] = (data["Date"] - data["Swap date"]).dt.days

  # Filter window: 15 days before and after submission
  window_data = data[
      (data["Days_Diff"] >= -15) & (data["Days_Diff"] <= 15)
  ].copy()

  # Define standard 3G KPIs and optimization directions
  default_kpis = {
      "Call Setup Success Rate CS_OPTIMUM": "higher",
      "Call Setup Success Rate PS_OPTIMUM": "higher",
      "Call Drop Rate CS_OPTIMUM": "lower",
      "Call Drop Rate PS_OPTIMUM": "lower",
      "DL User throughput_OPTIMUM": "higher",
      "UL User throughput_OPTIMUM": "higher",
  }

  available_kpis = [k for k in default_kpis.keys() if k in window_data.columns]

  st.sidebar.header("2. Filter Options")
  selected_kpis = st.sidebar.multiselect(
      "Select KPIs to Analyze",
      available_kpis,
      default=available_kpis[:4],
  )

  mode = st.sidebar.selectbox(
      "Select View Mode", ["Single Site Deep Dive", "All Sites Summary Report"]
  )

  if mode == "Single Site Deep Dive":
    site_list = window_data["Matched_Site"].unique()
    selected_site = st.sidebar.selectbox("Select Site", site_list)

    st.header(f"Detailed Site Evaluation: {selected_site}")
    site_subset = window_data[window_data["Matched_Site"] == selected_site].sort_values("Date")
    sub_date = site_subset["Swap date"].iloc[0]

    st.markdown(f"**Submission Date:** {sub_date.strftime('%Y-%m-%d')}")

    # Evaluate KPIs
    results = []
    for kpi in selected_kpis:
      direction = default_kpis.get(kpi, "higher")
      pre_subset = site_subset[
          (site_subset["Days_Diff"] >= -15) & (site_subset["Days_Diff"] < 0)
      ][kpi]
      post_subset = site_subset[
          (site_subset["Days_Diff"] > 0) & (site_subset["Days_Diff"] <= 15)
      ][kpi]

      pre_val = pre_subset.mean() if not pre_subset.empty else np.nan
      post_val = post_subset.mean() if not post_subset.empty else np.nan

      if pd.isna(pre_val) or pd.isna(post_val):
        status = "INSUFFICIENT DATA"
      elif direction == "higher":
        status = "ACCEPTED" if post_val >= pre_val else "REJECTED"
      else:
        status = "ACCEPTED" if post_val <= pre_val else "REJECTED"

      results.append({
          "KPI": kpi,
          "Pre-Submission Avg (-15d)": (
              round(pre_val, 2) if not pd.isna(pre_val) else "N/A"
          ),
          "Post-Submission Avg (+15d)": (
              round(post_val, 2) if not pd.isna(post_val) else "N/A"
          ),
          "Optimization Direction": direction.upper(),
          "Status": status,
      })

    res_df = pd.DataFrame(results)
    st.table(res_df)

    # Trend Graphs with Vertical Red Submission Line
    st.subheader("📊 15-Day Pre/Post KPI Trend Graphs")
    for kpi in selected_kpis:
      fig, ax = plt.subplots(figsize=(10, 3.5))
      ax.plot(
          site_subset["Date"],
          site_subset[kpi],
          marker="o",
          linestyle="-",
          color="#1f77b4",
          label=kpi,
      )
      ax.axvline(
          x=sub_date,
          color="red",
          linestyle="--",
          linewidth=2.5,
          label="Submission Date",
      )
      ax.set_title(f"{kpi} Trend for {selected_site}")
      ax.set_xlabel("Date")
      ax.set_ylabel(kpi)
      ax.legend(loc="upper left")
      ax.grid(True, linestyle=":", alpha=0.6)
      st.pyplot(fig)

  elif mode == "All Sites Summary Report":
    st.header("📋 Bulk Site Acceptance Summary Report")

    summary_list = []
    for site in window_data["Matched_Site"].unique():
      site_subset = window_data[window_data["Matched_Site"] == site]
      sub_date = site_subset["Swap date"].iloc[0]
      site_status = "ACCEPTED"
      failed_kpis = []

      for kpi in selected_kpis:
        direction = default_kpis.get(kpi, "higher")
        pre_val = site_subset[
            (site_subset["Days_Diff"] >= -15) & (site_subset["Days_Diff"] < 0)
        ][kpi].mean()
        post_val = site_subset[
            (site_subset["Days_Diff"] > 0) & (site_subset["Days_Diff"] <= 15)
        ][kpi].mean()

        if not pd.isna(pre_val) and not pd.isna(post_val):
          if direction == "higher" and post_val < pre_val:
            site_status = "REJECTED"
            failed_kpis.append(f"{kpi} (Dropped)")
          elif direction == "lower" and post_val > pre_val:
            site_status = "REJECTED"
            failed_kpis.append(f"{kpi} (Increased)")

      summary_list.append({
          "Site": site,
          "Submission Date": sub_date.strftime("%Y-%m-%d"),
          "Final Status": site_status,
          "Remarks": (
              ", ".join(failed_kpis) if failed_kpis else "All Selected KPIs Met"
          ),
      })

    summary_df = pd.DataFrame(summary_list)
    st.dataframe(summary_df, use_container_width=True)

    # Download Button
    csv_data = summary_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Full Acceptance Report (CSV)",
        data=csv_data,
        file_name="3G_Batch_Acceptance_Report.csv",
        mime="text/csv",
    )

else:
  st.info(
      "👉 Please upload both your **KPI Report (.xlsx)** and **Submission"
      " Dates (.xlsx)** using the sidebar to begin."
  )