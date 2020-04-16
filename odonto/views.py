"""
Odonto views
"""
import datetime
import json
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from odonto import episode_categories
from odonto import models
from opal.models import Episode, Patient


def has_open_fp17(patient):
    return patient.episode_set.filter(
        category_name='FP17').exclude(
            stage__in=['New', 'Submitted']).exists()


def has_open_fp17o(patient):
    return patient.episode_set.filter(
        category_name='FP17O').exclude(
            stage__in=['New', 'Submitted']).exists()


class OpenFP17s(TemplateView):
    template_name = "open_list.html"

    def get_fp17s(self):
        qs = Episode.objects.filter(stage="Open")
        qs = episode_categories.get_episodes_for_user(
            qs, self.request.user
        )

        unsubmitted = episode_categories.get_unsubmitted_fp17_and_fp17os(qs)
        unsubmitted_ids = unsubmitted.values_list("id", flat=True)
        return qs.exclude(id__in=unsubmitted_ids)


class UnsubmittedFP17s(LoginRequiredMixin, TemplateView):
    template_name = "unsubmitted_list.html"

    def get_fp17s(self):
        qs = Episode.objects.all()
        qs = episode_categories.get_episodes_for_user(
            qs, self.request.user
        )
        return episode_categories.get_unsubmitted_fp17_and_fp17os_for_user(
            self.request.user
        )


class FP17SummaryDetailView(LoginRequiredMixin, DetailView):
    model = Episode
    template_name = 'fp17_summary.html'


class ViewFP17DetailView(LoginRequiredMixin, DetailView):
    model = Episode
    template_name = 'view_fp17.html'


class FP17OSummaryDetailView(LoginRequiredMixin, DetailView):
    model = Episode
    template_name = 'fp17_o_summary.html'


class ViewFP17ODetailView(LoginRequiredMixin, DetailView):
    model = Episode
    template_name = 'view_fp17_o.html'


class Stats(LoginRequiredMixin, TemplateView):
    template_name = "stats.html"
    def get_current_financial_year(self):
        today = datetime.date.today()
        if today.month > 3:
            return (
                datetime.date(today.year, 4, 1),
                today
            )
        return (
            datetime.date(today.year-1, 4, 1),
            today
        )

    def get_previous_financial_year(self):
        current_start = self.get_current_financial_year()[0]
        return (
            datetime.date(
                current_start.year-1, current_start.month, current_start.day
            ),
            current_start - datetime.timedelta(1)
        )

    def get_fp17_qs(self, date_range):
        return Episode.objects.filter(
            category_name=episode_categories.FP17Episode.display_name
        ).filter(
            fp17incompletetreatment__completion_or_last_visit__range=date_range
        )

    def get_successful_fp17s(self, date_range):
        return episode_categories.FP17Episode.get_successful_episodes(
            self.get_fp17_qs(date_range)
        )

    def get_fp17o_qs(self, date_range):
        completed = Episode.objects.filter(
            category_name=episode_categories.FP17OEpisode.display_name
        ).exclude(
            orthodontictreatment__completion_type=None
        ).filter(
            orthodontictreatment__date_of_completion__range=date_range
        ).values_list('id', flat=True)
        assessment = Episode.objects.filter(
            category_name=episode_categories.FP17OEpisode.display_name
        ).filter(
            orthodontictreatment__completion_type=None
        ).filter(
            orthodonticassessment__date_of_assessment__range=date_range
        ).values_list('id', flat=True)
        episode_ids = set(list(completed) + list(assessment))
        return Episode.objects.filter(id__in=episode_ids)

    def get_successful_fp17os(self, date_range):
        return episode_categories.FP17OEpisode.get_successful_episodes(
            self.get_fp17o_qs(date_range)
        )

    def month_iterator(self, start_date):
        for i in range(0, 12):
            date_range = (
                start_date + relativedelta(months=i),
                start_date + relativedelta(months=i+1) - datetime.timedelta(1)
            )
            yield date_range

    def get_month_totals(self):
        result = {}
        monthly_claims = []
        time_periods = {
            "current": self.get_current_financial_year(),
            "previous": self.get_previous_financial_year()
        }
        for period_name, period_range in time_periods.items():
            monthly_claims = []
            for date_range in self.month_iterator(period_range[0]):
                successful_fp17o_count = self.get_successful_fp17os(date_range).count()
                successful_fp17_count = self.get_successful_fp17s(date_range).count()
                monthly_claims.append(
                    successful_fp17o_count + successful_fp17_count
                )
            result[period_name] = monthly_claims
        return result

    def get_state_counts(self):
        current_financial_year = self.get_current_financial_year()
        return {
            "fp17s": {
                "total": self.get_fp17_qs(current_financial_year).count(),
                "submitted": self.get_successful_fp17s(current_financial_year).count(),
                "open": self.get_fp17_qs(current_financial_year).filter(
                    stage=episode_categories.FP17Episode.OPEN
                ).count()
            },
            "fp17os": {
                "total": self.get_fp17o_qs(current_financial_year).count(),
                "submitted": self.get_successful_fp17os(current_financial_year).count(),
                "open": self.get_fp17o_qs(current_financial_year).filter(
                    stage=episode_categories.FP17OEpisode.OPEN
                ).count()
            }
        }

    def get_uoa_data(self):
        current_financial_year = self.get_current_financial_year()
        time_periods = {
            "current": self.get_current_financial_year(),
            "previous": self.get_previous_financial_year()
        }
        by_period = defaultdict(list)
        by_performer = defaultdict(int)

        for period_name, period_range in time_periods.items():
            for date_range in self.month_iterator(period_range[0]):
                fp17os = self.get_successful_fp17os(date_range)
                fp17os = fp17os.prefetch_related(
                    'orthodonticassessment_set',
                    'orthodontictreatment_set',
                    'fp17dentalcareprovider_set',
                )
                month_uoa_total = 0
                for fp17o in fp17os:
                    uoa = fp17o.category.uoa()
                    if not uoa:
                        continue

                    month_uoa_total += uoa
                    if period_name == "current":
                        performer = fp17o.fp17dentalcareprovider_set.all()[0].performer
                        by_performer[performer] += uoa
                by_period[period_name].append(month_uoa_total)
        return by_period, by_performer

    def get_uda_data(self):
        current_financial_year = self.get_current_financial_year()
        time_periods = {
            "current": self.get_current_financial_year(),
            "previous": self.get_previous_financial_year()
        }
        by_period = defaultdict(list)
        by_performer = defaultdict(lambda: defaultdict(int))

        for period_name, period_range in time_periods.items():
            for date_range in self.month_iterator(period_range[0]):
                fp17s = self.get_successful_fp17s(date_range)
                fp17s = fp17s.prefetch_related(
                    'fp17treatmentcategory_set',
                    'fp17dentalcareprovider_set'
                )
                month_uda_total = 0
                for fp17 in fp17s:
                    uda = fp17.category.uda()
                    if not uda:
                        continue

                    month_uda_total += uda
                    if period_name == "current":
                        treatment = fp17.fp17treatmentcategory_set.all()[0]
                        performer = fp17.fp17dentalcareprovider_set.all()[0].performer
                        by_performer[performer]["uda"] += uda
                        by_performer[performer][treatment.treatment_category] += 1
                by_period[period_name].append(round(month_uda_total))
        return by_period, by_performer

    def aggregate_performer_information(self, uda_by_performer, uoa_by_performer):
        result = []
        uda_performers = list(uda_by_performer.keys())
        uoa_performers = list(uoa_by_performer.keys())
        performers = list(set(uda_performers + uoa_performers))
        performers = sorted(performers)
        fp17s = self.get_successful_fp17s(
            self.get_current_financial_year()
        )

        for performer in performers:
            row = {"name": performer}
            fp17_performer = uda_by_performer.get(performer, {})
            row["uda"] = round(fp17_performer.get("uda", 0))
            row["band_1"] = fp17_performer.get(
                models.Fp17TreatmentCategory.BAND_1, 0
            )
            row["band_2"] = fp17_performer.get(
                models.Fp17TreatmentCategory.BAND_2, 0
            )
            row["band_3"] = fp17_performer.get(
                models.Fp17TreatmentCategory.BAND_3, 0
            )
            row["uoa"] = uoa_by_performer.get(performer, 0)
            result.append(row)
        return result

    def get_context_data(self):
        current_financial_year = self.get_current_financial_year()
        previous_financial_year = self.get_previous_financial_year()
        uda_by_period, uda_by_performer = self.get_uda_data()
        uoa_by_period, uoa_by_performer = self.get_uoa_data()
        performer_info = self.aggregate_performer_information(
            uda_by_performer, uoa_by_performer
        )
        current = "{}-{}".format(
            current_financial_year[0].year,
            current_financial_year[0].year + 1,
        )
        previous = "{}-{}".format(
            previous_financial_year[0].year,
            previous_financial_year[0].year + 1,
        )
        return {
            "current": current,
            "previous": previous,
            "state_counts": self.get_state_counts(),
            "month_totals": json.dumps(self.get_month_totals()),
            "uda_info": {
                "total":  sum(uda_by_period["current"]),
                "by_period": json.dumps(uda_by_period)
            },
            "uoa_info": {
                "total":  sum(uoa_by_period["current"]),
                "by_period": json.dumps(uoa_by_period)
            },
            "performer_info": performer_info
        }