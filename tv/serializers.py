from rest_framework import serializers
from .models import Video, Advertisement, Schedule, LiveStream


class VideoSerializer(serializers.ModelSerializer):
    duration_display = serializers.SerializerMethodField()
    class Meta:
        model = Video
        fields = '__all__'
    def get_duration_display(self, obj):
        return obj.duration_display()


class AdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Advertisement
        fields = '__all__'


class ScheduleSerializer(serializers.ModelSerializer):
    start_time_str = serializers.SerializerMethodField()
    class Meta:
        model = Schedule
        fields = '__all__'
    def get_start_time_str(self, obj):
        return obj.start_time.strftime('%H:%M')


class LiveStreamSerializer(serializers.ModelSerializer):
    embed = serializers.SerializerMethodField()
    class Meta:
        model = LiveStream
        fields = '__all__'
    def get_embed(self, obj):
        return obj.get_embed_url()
